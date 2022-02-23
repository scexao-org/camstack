// console/misc/common.cpp
//

#include "dcam_utils.h"

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stddef.h>

#ifndef ASSERT
#define ASSERT(c)
#endif

// ----------------------------------------------------------------

int my_dcamdev_string(DCAMERR* err, HDCAM hdcam, int32 idStr, char *text, int32 textbytes)
{
	DCAMDEV_STRING param;
	memset(&param, 0, sizeof(param));
	param.size = sizeof(param);
	param.text = text;
	param.textbytes = textbytes;
	param.iString = idStr;

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
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_MODEL)\n");
	}
	else if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_CAMERAID, cameraid, sizeof(cameraid)))
	{
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_CAMERAID)\n");
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
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_VENDOR)\n");
	else
		printf("DCAM_IDSTR_VENDOR         = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_MODEL, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_MODEL)\n");
	else
		printf("DCAM_IDSTR_MODEL          = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_CAMERAID, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_CAMERAID)\n");
	else
		printf("DCAM_IDSTR_CAMERAID       = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_BUS, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_BUS)\n");
	else
		printf("DCAM_IDSTR_BUS            = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_CAMERAVERSION, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_CAMERAVERSION)\n");
	else
		printf("DCAM_IDSTR_CAMERAVERSION  = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_DRIVERVERSION, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_DRIVERVERSION)\n");
	else
		printf("DCAM_IDSTR_DRIVERVERSION  = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_MODULEVERSION, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_MODULEVERSION)\n");
	else
		printf("DCAM_IDSTR_MODULEVERSION  = %s\n", buf);

	if (!my_dcamdev_string(&err, hdcam, DCAM_IDSTR_DCAMAPIVERSION, buf, sizeof(buf)))
		dcamcon_show_dcamerr(hdcam, err, "dcamdev_getstring(DCAM_IDSTR_DCAMAPIVERSION)\n");
	else
		printf("DCAM_IDSTR_DCAMAPIVERSION = %s\n", buf);
}

// ----------------------------------------------------------------
// initialize DCAM-API and get HDCAM camera handle.

HDCAM dcamcon_init_open(int cam_num)
{
	// Initialize DCAM-API ver 4.0
	DCAMAPI_INIT apiinit;
	memset(&apiinit, 0, sizeof(apiinit));
	apiinit.size = sizeof(apiinit);

	DCAMERR err;
	err = dcamapi_init(&apiinit);
	if (err != 1)
	{
		// failure
		dcamcon_show_dcamerr(NULL, err, "dcamapi_init()");
		return NULL;
	}

	int32 nDevice = apiinit.iDeviceCount;
	ASSERT(nDevice > 0); // nDevice must be larger than 0

	// show all camera information by text
    printf("DCAM: enumerating cameras [found %d]\n", nDevice);
	for (int iDevice = 0; iDevice < nDevice; iDevice++)
	{
        printf("Cam %d:   ", iDevice);
		dcamcon_show_dcamdev_info((HDCAM) iDevice);
	}
    printf("----\n");

	if (0 <= cam_num && cam_num < nDevice)
	{
		// open specified camera
		DCAMDEV_OPEN devopen;
		memset(&devopen, 0, sizeof(devopen));
		devopen.size = sizeof(devopen);
		devopen.index = cam_num;
		err = dcamdev_open(&devopen);

		if (err != 0)
		{
			HDCAM hdcam = devopen.hdcam;
            printf("Succesful open on camera %d:\n", cam_num);
            dcamcon_show_dcamdev_info((HDCAM) cam_num);
			dcamcon_show_dcamdev_info_detail(hdcam);
            printf("----\n");

			// SUCCESS
			return hdcam;
		}

		dcamcon_show_dcamerr((HDCAM) cam_num, err, "dcamdev_open()");
	} else {
        printf("Invalid camera number: %d ?\n", cam_num);
    }

	// FAILURE - uninitialize DCAM-API
	dcamapi_uninit();
	return NULL;
}
