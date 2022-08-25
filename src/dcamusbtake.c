
#define _GNU_SOURCE

#include <sched.h>
#include <signal.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "ImageStreamIO.h"
#include "ImageStruct.h"

#include "dcam_utils.h"
#include "dcamapi4.h"
#include "dcamprop.h"

static int end_signaled = 0; // termination flag for funcs

// Termination function for SIGINT callback
static void end_me(int dummy)
{
    end_signaled = 1;
}

static void usage(char *progname, char *errmsg);

static void set_rt_priority();

static void params_parse_and_set(HDCAM cam, IMAGE params_img, BOOL flag);

int main(int argc, char **argv)
{
    // register interrupt signal to terminate the main loop
    signal(SIGINT, end_me);

    int   lcount;
    int   unit = 0;
    char *progname;
    int   numbufs = 4;

    int loops = 1;
    int width, isiowidth, bytewidth, height, depth;
    // width: EDT image width (px.)
    // isiowidth: final image width (px.)
    // bytewidth: image width (bytes)

    double dcam_retval;

    char streamname[200];
    char streamname_feedback[200];

    double          meas_frate = 0.0; // Measured framerate, updated each frame
    double          meas_frate_gain = 0.01; // smoothing for meas_frate
    struct timespec time1;
    struct timespec time2;
    double          time_elapsed;

    // Set RTprio and UID stuff - may need to migrate this after
    // arg parsing if we make prio and cset settable from args.
    set_rt_priority();

    int REUSE_SHM      = 0;
    int STREAMNAMEINIT = 0;

    progname = argv[0];

    /*
   * process command line arguments
   */
    --argc;
    ++argv;
    while (argc && ((argv[0][0] == '-') || (argv[0][0] == '/')))
    {
        switch (argv[0][1])
        {
        case 'R':
            REUSE_SHM = 1;
            break;

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

    IMAGE     image;     // pointer to array of images
    IMAGE     image_prm; // pointer to array of images
    int       semid_prm;
    uint8_t   atype = _DATATYPE_UINT16; // data type
    long      naxis;                    // number of axis
    uint32_t *imsize;                   // image size
    int       shared;                   // 1 if image in shared memory
    int       NBkw;                     // number of keywords supported

    /*
  Open DCAM !
  */

    HDCAM cam = dcamcon_init_open(unit);
    if (cam == NULL) // failed open DCAM handle
    {
        exit(1);
    }

    // Initialize name
    if (STREAMNAMEINIT == 0)
    {
        sprintf(streamname, "hdcam%d", unit);
    }

    // Open the parameter-feedback SHM
    strcpy(streamname_feedback, streamname);
    strcat(streamname_feedback, "_params_fb");
    ImageStreamIO_openIm(&image_prm, streamname_feedback);
    semid_prm = ImageStreamIO_getsemwaitindex(&image_prm, -1);

    params_parse_and_set(cam,
                         image_prm,
                         TRUE); // TRUE: return mode, FALSE: print mode
    ImageStreamIO_semflush(&image_prm, semid_prm);

    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_SUBARRAYHSIZE, &dcam_retval),
        cam,
        1);
    width = (int) dcam_retval;
    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_SUBARRAYVSIZE, &dcam_retval),
        cam,
        1);
    height = (int) dcam_retval;
    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_IMAGE_PIXELTYPE, &dcam_retval),
        cam,
        1);
    DCAM_PIXELTYPE pxtype = (DCAM_PIXELTYPE) dcam_retval;
    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_SUBARRAYMODE, &dcam_retval),
        cam,
        1);
    printf("Subarray mode: %ld\n", (long) dcam_retval);
    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_EXPOSURETIME, &dcam_retval),
        cam,
        1);
    printf("Exposure: %f\n", (float) dcam_retval);
    CHECK_DCAM_ERR_EXIT(dcamprop_getvalue(cam,
                                          DCAM_IDPROP_INTERNAL_FRAMEINTERVAL,
                                          &dcam_retval),
                        cam,
                        1);
    printf("Internal frame interval: %f\n", (float) dcam_retval);
    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_INTERNALFRAMERATE, &dcam_retval),
        cam,
        1);
    printf("Internal framerate: %f\n", (float) dcam_retval);

    CHECK_DCAM_ERR_EXIT(
        dcamprop_getvalue(cam, DCAM_IDPROP_SENSORTEMPERATURE, &dcam_retval),
        cam,
        1);
    printf("TEMPERATURE: %f\n", (float) dcam_retval);

    if (pxtype == DCAM_PIXELTYPE_MONO16)
    {
        atype = _DATATYPE_UINT16;
        depth = 16;
    }
    else if (pxtype == DCAM_PIXELTYPE_MONO8)
    {
        atype = _DATATYPE_UINT8;
        depth = 8;
    }
    else
    {
        printf("Unusable pixel type.\n");
        CHECK_DCAM_ERR_EXIT(0, cam, 1);
    }

    isiowidth = width;
    bytewidth = (atype == _DATATYPE_UINT8) ? isiowidth : isiowidth * 2;

    printf("Size (edt)  : %d x %d\n", width, height);
    printf("Size (isio) : %d x %d\n", isiowidth, height);
    printf("Camera type :");
    dcamcon_show_dcamdev_info(cam);
    printf("\n");
    fflush(stdout);

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
                               0);
        free(imsize);
    }

    // Add keywords
    int N_KEYWORDS = 4;

    // Warning: the order of *kws* may change, because we're gonna allocate the
    // other ones from python.
    const char *KW_NAMES[] = {"MFRATE", "_MAQTIME", "_FGSIZE1", "_FGSIZE2"};
    const char  KW_TYPES[] = {'D', 'L', 'L', 'L'};
    const char *KW_COM[]   = {"Measured frame rate (Hz)",
                            "Frame acq time (us, CLOCK_REALTIME)",
                            "Size of frame grabber for the X axis (pixel)",
                            "Size of frame grabber for the Y axis (pixel)"};

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

    printf(
        "reading %d image(s) from 'DCAM camera %d'\nwidth %d height %d depth "
        "%d\n",
        loops,
        unit,
        width,
        height,
        depth);

    // Open the waitopen (?)
    DCAMWAIT_OPEN dcam_waitopen;
    memset(&dcam_waitopen, 0, sizeof(dcam_waitopen));
    dcam_waitopen.size  = sizeof(dcam_waitopen);
    dcam_waitopen.hdcam = cam;
    CHECK_DCAM_ERR_EXIT(dcamwait_open(&dcam_waitopen), cam, 1);
    // Allocate buffers
    CHECK_DCAM_ERR_EXIT(dcambuf_alloc(cam, numbufs),
                        cam,
                        1); // TODO we should do a buffer release somehow?
    // Start acquisiton
    CHECK_DCAM_ERR_EXIT(dcamcap_start(cam, DCAMCAP_START_SEQUENCE), cam, 1);

    // Whatever DCAMWAIT_START and DCAMCAP_TRANSFERINFO are...
    DCAMWAIT_START dcam_waitstart;
    memset(&dcam_waitstart, 0, sizeof(dcam_waitstart));
    dcam_waitstart.size      = sizeof(dcam_waitstart);
    dcam_waitstart.eventmask = DCAMWAIT_CAPEVENT_FRAMEREADY;
    dcam_waitstart.timeout   = 10000;
    DCAMCAP_TRANSFERINFO dcam_captransferinfo;
    memset(&dcam_captransferinfo, 0, sizeof(dcam_captransferinfo));
    dcam_captransferinfo.size = sizeof(dcam_captransferinfo);

    // Prepare an output buffer wrapper structure
    DCAMBUF_FRAME bufframe;
    memset(&bufframe, 0, sizeof(bufframe));
    bufframe.size     = sizeof(bufframe);
    bufframe.buf      = image.array.raw; // MAGIC !!
    bufframe.rowbytes = bytewidth;
    bufframe.left     = 0;
    bufframe.top      = 0;
    bufframe.width    = width;
    bufframe.height   = height;

    // Prep time measurement
    clock_gettime(CLOCK_REALTIME, &time1);

    printf("\n");
    lcount     = 0;
    int loopOK = 1;

    // We post control_shm to let the camstack manager know that the new SHM is
    // ready This mechanism is used only in this backend for camstack because
    // re-starting dcam API is pretty slow so we want a feedback that it's over
    ImageStreamIO_UpdateIm(&image_prm);
    // Problem: when we do this, this will trigger the parameter update in the
    // loop... Let's click that semaphore
    ImageStreamIO_semtrywait(&image_prm, semid_prm);

    // Main loop. What happens if we have a end_signaled but we're caught in a
    // timeout? kill_taker from python will only wait 0.1 sec between Ctrl-C and a
    // kill -9
    while (end_signaled == 0 && loopOK == 1)
    {
        // Check parameters to update ?
        if (0 == ImageStreamIO_semtrywait(&image_prm, semid_prm))
        {
            printf("Touching the params !\n");
            params_parse_and_set(cam, image_prm, FALSE);
            ImageStreamIO_semflush(&image_prm, semid_prm);
        }

        // ACQUIRE FRAME
        // TODO Check this for timeouts and joyous stuff !
        CHECK_DCAM_ERR_PRINT(
            dcamwait_start(dcam_waitopen.hwait, &dcam_waitstart),
            cam);
        CHECK_DCAM_ERR_PRINT(dcamcap_transferinfo(cam, &dcam_captransferinfo),
                             cam);

        // TODO Check those for overruns/underruns
        if (lcount % 5000 == 0)
        {
            printf("nNewestFrameIndex: %d -- ",
                   dcam_captransferinfo.nNewestFrameIndex);
            printf("frame: %d -- ", lcount);
            printf("captransferinfo.nFrameCount: %d\n",
                   dcam_captransferinfo.nFrameCount);
        }

        // printf("line = %d\n", __LINE__);
        fflush(stdout);

        image.md[0].write = 1; // set this flag to 1 when writing data

        bufframe.iFrame = dcam_captransferinfo.nNewestFrameIndex;

        // printf("Copying %d x %d bytes", bytewidth, height);
        dcambuf_copyframe(cam, &bufframe);

        // Compute and write the timing
        clock_gettime(CLOCK_REALTIME, &time2);
        time_elapsed = difftime(time2.tv_sec, time1.tv_sec);
        time_elapsed += (time2.tv_nsec - time1.tv_nsec) / 1e9;

        meas_frate *= (1.0 - meas_frate_gain);
        meas_frate += 1.0 / time_elapsed * meas_frate_gain;
        image.kw[KW_POS[0]].value.numf = (float) meas_frate; // MFRATE
        image.kw[KW_POS[1]].value.numl = ((long) time2.tv_sec * 1000000) +
                                         (time2.tv_nsec / 1000); // MACQTMUS

        // Post !
        ImageStreamIO_UpdateIm(&image);
        image.md[0].cnt1++;

        time1.tv_sec  = time2.tv_sec;
        time1.tv_nsec = time2.tv_nsec;

        lcount++;
        if (lcount == loops)
        {
            loopOK = 0;
        }
    }
    puts("");

    // Deinit, cleanup, exit.
    dcamcap_stop(cam);
    printf("A\n");
    dcambuf_release(cam, 0);
    printf("B\n");
    dcamwait_close(dcam_waitopen.hwait);
    printf("C\n");
    dcamdev_close(cam);
    printf("D\n");
    dcamapi_uninit();
    printf("E\n");

    printf("\n------\ndcamusbtake.c: successful exit.\n");
    // CHECK_DCAM_ERR_EXIT(0, cam, 1);

    exit(0);
}

static void params_parse_and_set(HDCAM cam, IMAGE params_img, BOOL flag)
{
    // Figure out in the data how many keywords are fresh for writing
    int    N_KEYWORDS = params_img.array.UI16[0];
    long   param_id;
    double dcam_retval;

    // Read keywords, send to camera
    for (int kw = 0; kw < N_KEYWORDS; ++kw)
    {
        param_id = strtol(params_img.kw[kw].name, NULL, 16);
        // Do we have the "get only" bit 32? & 0x80000000 to check it, &7fffffff to
        // filter it.
        if (!(param_id & 0x80000000))
        {
            printf("setting\n");
            if (flag)
            { // Die upon error
                printf("param_id %ld --- %s ; %ld ; %lf\n",
                       param_id,
                       params_img.kw[kw].value.valstr,
                       params_img.kw[kw].value.numl,
                       (float) params_img.kw[kw].value.numf);
                CHECK_DCAM_ERR_EXIT(
                    dcamprop_setvalue(cam,
                                      param_id,
                                      params_img.kw[kw].value.numf),
                    cam,
                    1);
            }
            else
            { // Print error and keep going
                printf("param_id %ld --- %s ; %ld ; %lf\n",
                       param_id,
                       params_img.kw[kw].value.valstr,
                       params_img.kw[kw].value.numl,
                       (float) params_img.kw[kw].value.numf);
                CHECK_DCAM_ERR_PRINT(
                    dcamprop_setvalue(cam,
                                      param_id,
                                      params_img.kw[kw].value.numf),
                    cam);
            }
        }

        // Now get the data back and write it in the SHM keyword !
        CHECK_DCAM_ERR_PRINT(
            dcamprop_getvalue(cam, param_id & 0x7ffffff, &dcam_retval),
            cam);
        params_img.kw[kw].value.numf = dcam_retval;
    }
}

static void usage(char *progname, char *errmsg)
{
    puts(errmsg);
    printf("%s: simple example program that acquires images from an\n",
           progname);
    printf("EDT digital imaging interface board (PCI DV, PCI DVK, etc.)\n");
    puts("");
    printf(
        "usage: %s [-n streamname] [-l loops] [-N numbufs] [-u unit] [-c "
        "channel]\n",
        progname);
    printf(
        "  -s streamname   output stream name (default: edtcam<unit><chan>\n");
    printf(
        "  -8              enable 8->16 bit casting mode, width divided by 2 "
        "- implies -U \n");
    printf("  -U              unsigned 16 bit output (default: signed)\n");
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
