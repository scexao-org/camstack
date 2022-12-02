// console/misc/common.cpp
//

#include "dcam_utils.h"

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdlib.h>

#include <errno.h>

#ifndef ASSERT
#define ASSERT(c)
#endif

// ----------------------------------------------------------------

int my_dcamdev_string(
    DCAMERR *err, HDCAM hdcam, int32 idStr, char *text, int32 textbytes)
{
    DCAMDEV_STRING param;
    memset(&param, 0, sizeof(param));
    param.size      = sizeof(param);
    param.text      = text;
    param.textbytes = textbytes;
    param.iString   = idStr;

    *err = dcamdev_getstring(hdcam, &param);
    return err != 0;
}

// ----------------------------------------------------------------

void dcamcon_show_dcamerr(HDCAM hdcam, DCAMERR errid, const char *apiname)
{
    char errtext[256];

    DCAMERR err;
    my_dcamdev_string(&err, hdcam, errid, errtext, sizeof(errtext));

    printf("FAILED: (DCAMERR)0x%08X %s @ %s", errid, errtext, apiname);

    printf("\n");
}

// ----------------------------------------------------------------

void dcamcon_show_dcamdev_info(HDCAM hdcam)
{
    char model[256];
    char cameraid[64];
    char bus[64];

    DCAMERR err;
    if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_MODEL, model, sizeof(model)))
    {
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_MODEL)\n");
    }
    else if (!my_dcamdev_string(&err,
                                hdcam,
                                DCAM_IDSTR_CAMERAID,
                                cameraid,
                                sizeof(cameraid)))
    {
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_CAMERAID)\n");
    }
    else if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_BUS, bus, sizeof(bus)))
    {
        dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_BUS)\n");
    }
    else
    {
        printf("%s (%s) on %s\n", model, cameraid, bus);
    }
}

// show HDCAM camera information by text.
void dcamcon_show_dcamdev_info_detail(HDCAM hdcam)
{
    char buf[256];

    DCAMERR err;
    if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_VENDOR, buf, sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_VENDOR)\n");
    else
        printf("DCAM_IDSTR_VENDOR         = %s\n", buf);

    if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_MODEL, buf, sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_MODEL)\n");
    else
        printf("DCAM_IDSTR_MODEL          = %s\n", buf);

    if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_CAMERAID, buf, sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_CAMERAID)\n");
    else
        printf("DCAM_IDSTR_CAMERAID       = %s\n", buf);

    if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_BUS, buf, sizeof(buf)))
        dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_BUS)\n");
    else
        printf("DCAM_IDSTR_BUS            = %s\n", buf);

    if (!my_dcamdev_string(&err,
                           hdcam,
                           DCAM_IDSTR_CAMERAVERSION,
                           buf,
                           sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_CAMERAVERSION)\n");
    else
        printf("DCAM_IDSTR_CAMERAVERSION  = %s\n", buf);

    if (!my_dcamdev_string(&err,
                           hdcam,
                           DCAM_IDSTR_DRIVERVERSION,
                           buf,
                           sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_DRIVERVERSION)\n");
    else
        printf("DCAM_IDSTR_DRIVERVERSION  = %s\n", buf);

    if (!my_dcamdev_string(&err,
                           hdcam,
                           DCAM_IDSTR_MODULEVERSION,
                           buf,
                           sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_MODULEVERSION)\n");
    else
        printf("DCAM_IDSTR_MODULEVERSION  = %s\n", buf);

    if (!my_dcamdev_string(&err,
                           hdcam,
                           DCAM_IDSTR_DCAMAPIVERSION,
                           buf,
                           sizeof(buf)))
        dcamcon_show_dcamerr(hdcam,
                             err,
                             "dcamdev_getstring(DCAM_IDSTR_DCAMAPIVERSION)\n");
    else
        printf("DCAM_IDSTR_DCAMAPIVERSION = %s\n", buf);
}

// ----------------------------------------------------------------
// initialize DCAM-API and get HDCAM camera handle.

int dcamcon_init_upto_index(int max_index)
{
    // Scan the API after disabling framegrabbers >= max_index.
    // Max index < 0 will ignore this feature (for scan bus and print)

    // Initialize DCAM-API ver 4.0
    DCAMAPI_INIT apiinit;
    DCAMERR      err;
    memset(&apiinit, 0, sizeof(apiinit));
    apiinit.size = sizeof(apiinit);

    int32 initoption[]      = {DCAMAPI_INITOPTION_APIVER__LATEST,
                          DCAMAPI_INITOPTION_ENDMARK};
    apiinit.initoption      = initoption;
    apiinit.initoptionbytes = sizeof(initoption);

    // Disable framegrabbers of index >= max_index
    if (max_index >= 0)
    {
        toggle_readable_all_aslenum_devices(FALSE);
        for (int ii = 0; ii < max_index; ++ii)
        {
            enable_one_aslenum_device(ii);
        }
    }

    err = dcamapi_init(&apiinit);

    // Re-enable framegrabbers of index >= max_index
    if (max_index >= 0)
    {
        toggle_readable_all_aslenum_devices(TRUE);
    }

    if (err != DCAMERR_SUCCESS && err != DCAMERR_NOCAMERA)
    { // NOCAMERA error is considered success
        dcamcon_show_dcamerr(NULL, err, "dcamapi_init()");
        return EXIT_FAILURE;
    }

    // show all camera information by text
    printf("DCAM: enumerating cameras [found %d]\n", apiinit.iDeviceCount);
    for (int iDevice = 0; iDevice < apiinit.iDeviceCount; iDevice++)
    {
        printf("Cam %d:   ", iDevice);
        dcamcon_show_dcamdev_info_detail((HDCAM) (long) iDevice);
    }
    printf("----\n");

    return EXIT_SUCCESS;
}

HDCAM dcamcon_opencam(int cam_num)
{
    DCAMERR err;

    // open specified camera
    DCAMDEV_OPEN devopen;
    memset(&devopen, 0, sizeof(devopen));
    devopen.size = sizeof(devopen);
    devopen.index = cam_num;
    err = dcamdev_open(&devopen);

    if (err != DCAMERR_SUCCESS)
    {
        dcamcon_show_dcamerr((HDCAM) (long) cam_num, err, "dcamdev_open()");
        return NULL; // Caller should de-init API and quit.
    }

    HDCAM hdcam = devopen.hdcam;
    printf("Succesful open on camera %d:\n", cam_num);
    dcamcon_show_dcamdev_info((HDCAM) (long) 0);
    dcamcon_show_dcamdev_info_detail(hdcam);
    printf("----\n");

    // SUCCESS
    return hdcam;

}

void toggle_readable_all_aslenum_devices(BOOL enable)
{
    /*
    Now this is a hack to enable having only ONE camera plugged to
    the system by the time we end up calling dcamapi_init()
    This avoids letting the API get a lock on ALL cameras.
    And then subsequent processes can still get access to the other ones.

    Essentially, we're doing
        chmod u-r /dev/aslenum*
    */
    int mode_disable = strtol("0266", 0, 8);
    int mode_enable  = strtol("0666", 0, 8);

    char filename[100];
    int  device_idx = 0;
    int  ret_code   = 0;
    while (ret_code == 0)
    {
        sprintf(filename, "/dev/aslenum%d", device_idx++);
        if (enable)
        {
            ret_code = chmod(filename, mode_enable);
        }
        else
        {
            ret_code = chmod(filename, mode_disable);
        }
    }
    // We're expeting to error for the n-th + 1 device, that does not exist.
    // But if we EPERM (on an existing device), that mean we need to chown.
    if (ret_code == -1 && errno == EPERM) {
        printf("Multicam hack errno = EPERM. Maybe you need to 'chown alala:alala /dev/aslenum*' ?\n");
    }
}



void enable_one_aslenum_device(int index)
{
    int  mode_enable = strtol("0666", 0, 8);
    char filename[100];
    sprintf(filename, "/dev/aslenum%d", index);
    chmod(filename, mode_enable);
};

void disable_one_aslenum_device(int index)
{
    int  mode_enable = strtol("0266", 0, 8);
    char filename[100];
    sprintf(filename, "/dev/aslenum%d", index);
    chmod(filename, mode_enable);
};