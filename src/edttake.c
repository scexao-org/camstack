/*
 *
 *
 * Compile with:
 * gcc imgtake.c -o imgtake -I/opt/EDTpdv
 * -I/home/scexao/src/cacao/src/ImageStreamIO
 * -I/home/scexao/src/cacao/src
 * /home/scexao/src/cacao/src/ImageStreamIO/ImageStreamIO.c
 *
 * /opt/EDTpdv/libpdv.a -lm -lpthread -ldl
 *
 *
 */

#define _GNU_SOURCE

#include <sched.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>

#include "ImageStreamIO.h"
#include "ImageStruct.h"
#include "edtinc.h"

static int end_signaled = 0; // termination flag for funcs

// Termination function for SIGINT callback
static void end_me(int dummy)
{
    end_signaled = 1;
}

static void usage(char *progname, char *errmsg);

static void set_rt_priority();

int main(int argc, char **argv)
{
    // register interrupt signal to terminate the main loop
    signal(SIGINT, end_me);

    int     i;
    int     unit = 0;
    int     overrun, overruns = 0;
    int     timeout;
    int     timeouts, last_timeouts = 0;
    int     images_skipped     = 0;
    int     recovering_timeout = FALSE;
    char   *progname;
    char   *cameratype;
    int     numbufs = 4;
    u_char *image_p;
    PdvDev *pdv_p;
    char    errstr[64];
    int     loops = 1;
    int     width, isiowidth, bytewidth, height, depth;
    // width: EDT image width (px.)
    // isiowidth: final image width (px.)
    // bytewidth: image width (bytes)
    char edt_devname[128];
    int  channel = 0; // same as cam
    char streamname[200];

    double          meas_frate = 0.0; // Measured framerate, updated each frame
    double          meas_frate_gain = 0.01; // smoothing for meas_frate
    long            time_acq_micros;
    long           *p_embed_acqtime;
    struct timespec time1;
    struct timespec time2;
    double          time_elapsed;

    // Set RTprio and UID stuff - may need to migrate this after
    // arg parsing if we make prio and cset settable from args.
    set_rt_priority();

    int REUSE_SHM         = 0;
    int UNSIGNED_OUT      = 0;
    int BYTESHORTCAST     = 0;
    int STREAMNAMEINIT    = 0;
    int EMBED_MICROSECOND = 0;

    progname = argv[0];

    edt_devname[0] = '\0';

    /*
   * process command line arguments
   */
    --argc;
    ++argv;
    while (argc && ((argv[0][0] == '-') || (argv[0][0] == '/')))
    {
        switch (argv[0][1])
        {
        case 'N':
            ++argv;
            --argc;
            if (argc < 1)
            {
                usage(progname,
                      "Error: option 'N' requires a numeric argument\n");
            }
            if ((argv[0][0] >= '0') && (argv[0][0] <= '9'))
            {
                numbufs = atoi(argv[0]);
            }
            else
            {
                usage(progname,
                      "Error: option 'N' requires a numeric argument\n");
            }
            break;

        case 'U':
            UNSIGNED_OUT = 1;
            break;

        case 't':
            EMBED_MICROSECOND = 1;
            break;

        case 'R':
            REUSE_SHM = 1;
            break;

        case '8':
            UNSIGNED_OUT  = 1;
            BYTESHORTCAST = 1;
            break;

        case 's':
            ++argv;
            --argc;
            if (argc < 1)
            {
                printf("Error: option 's' requires string argument\n");
            }
            strcpy(streamname, argv[0]);
            STREAMNAMEINIT = 1;
            break;

        case 'u':
            ++argv;
            --argc;
            if (argc < 1)
            {
                printf("Error: option 'u' requires a numeric argument (0-9)\n");
            }
            if ((argv[0][0] >= '0') && (argv[0][0] <= '9'))
            {
                unit = atoi(argv[0]);
            }
            else
            {
                printf("Error: option 'u' requires a numeric argument (0-9)\n");
            }
            break;

        case 'c':
            ++argv;
            --argc;
            if (argc < 1)
            {
                printf(
                    "Error: option 'c' requires a numeric argument (0 or 1)\n");
            }
            if ((argv[0][0] >= '0') && (argv[0][0] <= '2'))
            {
                channel = atoi(argv[0]);
            }
            else
            {
                printf(
                    "Error: option 'c' requires a numeric argument (0 or 1)\n");
            }
            break;

        case 'l':
            ++argv;
            --argc;
            if (argc < 1)
            {
                usage(progname,
                      "Error: option 'l' requires a numeric argument\n");
            }
            if ((argv[0][0] >= '0') && (argv[0][0] <= '9'))
            {
                loops = atoi(argv[0]);
            }
            else
            {
                usage(progname,
                      "Error: option 'l' requires a numeric argument\n");
            }
            break;

        case '-':
            if (strcmp(argv[0], "--help") == 0)
            {
                usage(progname, "");
                exit(0);
            }
            else
            {
                fprintf(stderr, "unknown option: %s\n", argv[0]);
                usage(progname, "");
                exit(1);
            }
            break;

        default:
            fprintf(stderr, "unknown flag -'%c'\n", argv[0][1]);
        case '?':
        case 'h':
            usage(progname, "");
            exit(0);
        }
        argc--;
        argv++;
    }

    /*
   * open the interface
   *
   * EDT_INTERFACE is defined in edtdef.h (included via edtinc.h)
   *
   * edt_parse_unit_channel and pdv_open_channel) are equivalent to
   * edt_parse_unit and pdv_open except for the extra channel arg and
   * would normally be 0 unless there's another camera (or simulator)
   * on the second channel (camera link) or daisy-chained RCI (PCI FOI)
   */

    if (edt_devname[0])
    {
        unit = edt_parse_unit_channel(edt_devname,
                                      edt_devname,
                                      EDT_INTERFACE,
                                      &channel);
    }
    else
    {
        strcpy(edt_devname, EDT_INTERFACE);
    }

    printf("edt_devname = %s   unit = %d    channel = %d\n",
           edt_devname,
           unit,
           channel);

    if ((pdv_p = pdv_open_channel(edt_devname, unit, channel)) == NULL)
    {
        sprintf(errstr,
                "pdv_open_channel(%s%d_%d)",
                edt_devname,
                unit,
                channel);
        pdv_perror(errstr);
        return (1);
    }

    pdv_flush_fifo(pdv_p);

    IMAGE     image;  // pointer to array of images
    uint8_t   atype;  // data type
    long      naxis;  // number of axis
    uint32_t *imsize; // image size
    int       shared; // 1 if image in shared memory
    int       NBkw;   // number of keywords supported

    width      = pdv_get_width(pdv_p);
    height     = pdv_get_height(pdv_p);
    depth      = pdv_get_depth(pdv_p);
    timeout    = pdv_get_timeout(pdv_p);
    cameratype = pdv_get_cameratype(pdv_p);

    isiowidth = (BYTESHORTCAST != 0) ? width / 2 : width;

    // Do we want 8 bit or 16 bit output (cast implies unsigned)?
    atype = ((BYTESHORTCAST != 0) || depth != 8) ? _DATATYPE_UINT16
                                                 : _DATATYPE_UINT8;
    // Do we want signed or unsigned 16 bit output ?
    if (atype == _DATATYPE_UINT8 && !UNSIGNED_OUT)
    {
        atype = _DATATYPE_INT8;
    }
    else if (atype == _DATATYPE_UINT16 && !UNSIGNED_OUT)
    {
        atype = _DATATYPE_INT16;
    }

    // 16 -> 16 OR 8 -> 16: bytewidth = isiowidth * 2
    // 8 -> 8: bytewidth = isiowidth
    // will be used to figure out the memcopy size
    bytewidth = (atype == _DATATYPE_UINT8) ? isiowidth : isiowidth * 2;

    printf("Size (edt)  : %d x %d\n", width, height);
    printf("Size (isio) : %d x %d\n", isiowidth, height);
    printf("Depth       : %d\n", depth);
    printf("Timeout     : %d\n", timeout);
    printf("Camera type : %s\n", cameratype);
    fflush(stdout);

    if (STREAMNAMEINIT == 0)
    {
        sprintf(streamname, "edtcam%d%d", unit, channel);
    }

    if (REUSE_SHM)
    {
        ImageStreamIO_openIm(&image, streamname);
    }
    else
    {
        // allocate memory for array of images
        // image = malloc(sizeof(IMAGE));
        naxis     = 2;
        imsize    = (uint32_t *) malloc(sizeof(uint32_t) * naxis);
        imsize[0] = isiowidth;
        imsize[1] = height;
        // image will be in shared memory
        shared = 1;
        // allocate space for keywords
        NBkw = 50;
        ImageStreamIO_createIm(&image,
                               streamname,
                               naxis,
                               imsize,
                               atype,
                               shared,
                               NBkw,
                               10);
        free(imsize);
    }

    // Make a pointer at 8th pixel to embed the acquisition time
    // This will really only work well on 16 bit output but hey.
    p_embed_acqtime = atype == _DATATYPE_UINT8 ? (long *) &image.array.UI8[8]
                                               : (long *) &image.array.UI16[8];

    // Add keywords
    int N_KEYWORDS = 4;

    // Warning: the order of *kws* may change, because we're gonna allocate the
    // other ones from python.
    const char *KW_NAMES[] =
        {"MFRATE",
         "_MAQTIME",
         "_FGSIZE1",
         "_FGSIZE2"}; // "tint", "fps", "DET-NSMP", "x0", "x1", "y0", "y1",
                      // "temp"}; // DET-NSMP is ex-NDR
    const char  KW_TYPES[] = {'D',
                             'L',
                             'L',
                             'L'}; // {'D', 'D', 'L', 'L', 'L', 'L', 'L', 'D'};
    const char *KW_COM[]   = {
        "Measured frame rate (Hz)",
        "Frame acq time (us, CLOCK_REALTIME)",
        "Size of frame grabber for the X axis (pixel)",
        "Size of frame grabber for the Y axis (pixel)"}; // {"exposure time",
    // "frame rate", "NDR",
    // "x0", "x1", "y0",
    // "y1", "detector
    // temperature"};

    int KW_POS[] = {0, 1, 2, 3};

    if (!REUSE_SHM)
    {
        for (int kw = 0; kw < N_KEYWORDS; ++kw)
        {
            strcpy(image.kw[kw].name, KW_NAMES[kw]);
            image.kw[kw].type = KW_TYPES[kw];
            strcpy(image.kw[kw].comment, KW_COM[kw]);
        }
    }
    else
    {
        for (int kw = 0; kw < image.md->NBkw; ++kw)
        {
            for (int i = 0; i < N_KEYWORDS; ++i)
            {
                if (strcmp(KW_NAMES[i], image.kw[kw].name) == 0)
                {
                    KW_POS[i] = kw;
                }
            }
        }
    }
    // Initial values
    image.kw[KW_POS[0]].value.numf = 0.0;
    image.kw[KW_POS[1]].value.numf = 0;
    image.kw[KW_POS[2]].value.numl = height;
    image.kw[KW_POS[3]].value.numl = isiowidth;

    /*
   * allocate four buffers for optimal pdv ring buffer pipeline (reduce if
   * memory is at a premium)
   */
    pdv_multibuf(pdv_p, numbufs);

    printf("reading %d image%s from '%s'\nwidth %d height %d depth %d\n",
           loops,
           loops == 1 ? "" : "s",
           cameratype,
           width,
           height,
           depth);

    /*
   * prestart the first image or images outside the loop to get the
   * pipeline going. Start multiple images unless force_single set in
   * config file, since some cameras (e.g. ones that need a gap between
   * images or that take a serial command to start every image) don't
   * tolerate queueing of multiple images
   */

    if (pdv_p->dd_p->force_single)
    {
        printf("Using pdv_start_image.\n");
        pdv_start_image(pdv_p);
    }
    else
    {
        printf("Using pdv_start_imageS\n");
        pdv_start_images(pdv_p, numbufs);
    }

    // Prep time measurement
    clock_gettime(CLOCK_REALTIME, &time1);

    printf("\n");
    i          = 0;
    int loopOK = 1;

    while (end_signaled == 0 && loopOK == 1)
    {
        /*
     * get the image and immediately start the next one (if not the last
     * time through the loop). Processing (saving to a file in this case)
     * can then occur in parallel with the next acquisition
     *
     * Must use pdv_wait_LAST_image, other than we get the last unread, which
     * may be an older frame.
     */

        image_p = pdv_wait_last_image(pdv_p, &images_skipped);

        if (images_skipped > 0)
        {
            printf("wait_last_image: %d misses\n", images_skipped);
        }

        if ((overrun = (edt_reg_read(pdv_p, PDV_STAT) &
                        PDV_OVERRUN))) // Does that work ??
        {
            ++overruns;
            printf("overrun @ %s", ctime((time_t *) &time1));
            recovering_timeout = TRUE;
        }

        pdv_start_image(pdv_p);
        timeouts = pdv_timeouts(pdv_p);

        /*
     * check for timeouts or data overruns -- timeouts occur when data
     * is lost, camera isn't hooked up, etc, and application programs
     * should always check for them. data overruns usually occur as a
     * result of a timeout but should be checked for separately since
     * ROI can sometimes mask timeouts
     */
        if (timeouts > last_timeouts)
        {
            /*
       * pdv_timeout_cleanup helps recover gracefully after a timeout,
       * particularly if multiple buffers were prestarted
       */
            clock_gettime(CLOCK_REALTIME, &time1);
            printf("timeout..... @ %s\n", ctime((time_t *) &time1));

            pdv_timeout_restart(pdv_p, TRUE);
            last_timeouts      = timeouts;
            recovering_timeout = TRUE;
            pdv_timeout_restart(pdv_p, TRUE);
            continue;
        }
        else if (recovering_timeout)
        {
            clock_gettime(CLOCK_REALTIME, &time1);
            printf("restarted... @ %s\n", ctime((time_t *) &time1));
            pdv_timeout_restart(pdv_p, TRUE);
            recovering_timeout = FALSE;
        }

        // printf("line = %d\n", __LINE__);
        fflush(stdout);

        image.md[0].write = 1; // set this flag to 1 when writing data
        // printf("Copying %d x %d bytes", bytewidth, height);
        memcpy(image.array.UI8, image_p, bytewidth * height);

        // Write the timing !
        clock_gettime(CLOCK_REALTIME, &time2);
        time_elapsed = difftime(time2.tv_sec, time1.tv_sec);
        time_elapsed += (time2.tv_nsec - time1.tv_nsec) / 1e9;

        meas_frate *= (1.0 - meas_frate_gain);
        // This is only CPU time - that sucks.
        meas_frate += 1.0 / time_elapsed * meas_frate_gain;

        time_acq_micros =
            ((long) time2.tv_sec * 1000000) + (time2.tv_nsec / 1000);
        if (EMBED_MICROSECOND)
        {
            *p_embed_acqtime =
                time_acq_micros; // Will go for 4 or 8 pixel dep if
                                 // type is int8 or int16
        }

        image.kw[KW_POS[0]].value.numf = (float) meas_frate; // MFRATE
        image.kw[KW_POS[1]].value.numl = time_acq_micros;    // _MAQTIME

        // Embed _MAQTIME in the image starting at pixel 12
        // This will take 8 bytes, which can be either 4 or 8 pixels

        // Post the sem and fix cnt1
        image.md[0].cnt1++;
        ImageStreamIO_UpdateIm(&image);

        time1.tv_sec  = time2.tv_sec;
        time1.tv_nsec = time2.tv_nsec;

        i++;
        if (i == loops)
        {
            loopOK = 0;
        }
    }
    puts("");

    printf("%d images %d timeouts %d overruns\n",
           loops,
           last_timeouts,
           overruns);

    /*
   * if we got timeouts it indicates there is a problem
   */
    if (last_timeouts)
    {
        printf("check camera and connections\n");
    }
    pdv_close(pdv_p);

    printf("\n------\nedttake.c: successful exit.\n");
    if (overruns || timeouts)
    {
        exit(2);
    }
    exit(0);
}

static void usage(char *progname, char *errmsg)
{
    puts(errmsg);
    printf("%s: simple example program that acquires images from an\n",
           progname);
    printf("EDT digital imaging interface board (PCI DV, PCI DVK, etc.)\n");
    puts("");
    printf(
        "usage: %s [-s streamname] [-l loops] [-N numbufs] [-u unit] [-c "
        "channel]\n",
        progname);
    printf(
        "  -s streamname   output stream name (default: edtcam<unit><chan>\n");
    printf(
        "  -8              enable 8->16 bit casting mode, width divided by 2 "
        "- implies -U \n");
    printf("  -U              unsigned 16 bit output (default: signed)\n");
    printf("  -t              embed microsecond grab tag\n");
    printf("  -u unit         set unit\n");
    printf("  -c chan         set channel (1 tap, 1 cable)\n");
    printf("  -l loops        number of loops (images to take)\n");
    printf(
        "  -N numbufs      number of ring buffers (see users guide) (default "
        "4)\n");
    printf("  -h              this help message\n");
    exit(1);
}

static void set_rt_priority()
{

    uid_t ruid; // Real UID (= user launching process at startup)
    uid_t euid; // Effective UID (= owner of executable at startup)
    uid_t suid; // Saved UID (= owner of executable at startup)

    int                RT_priority = 70; // any number from 0-99
    struct sched_param schedpar;
    int                ret;

    getresuid(&ruid, &euid, &suid);
    // This sets it to the privileges of the normal user
    ret = seteuid(ruid);
    if (ret != 0)
    {
        printf("setuid error\n");
    }

    schedpar.sched_priority = RT_priority;

    if (ret != 0)
    {
        printf("setuid error\n");
    }
    ret = seteuid(euid); // This goes up to maximum privileges
    sched_setscheduler(0,
                       SCHED_FIFO,
                       &schedpar); // other option is SCHED_RR, might be faster
    ret = seteuid(ruid);           // Go back to normal privileges
    if (ret != 0)
    {
        printf("setuid error\n");
    }
}
