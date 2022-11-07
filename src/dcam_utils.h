
#include "dcamapi4.h"
#include "dcamprop.h"
#include <sys/stat.h>

typedef unsigned int BOOL;

#define FALSE (BOOL) 0
#define TRUE  (BOOL) 1

void dcamcon_show_dcamerr(HDCAM hdcam, DCAMERR errid, const char *apiname);

int dcamcon_init_upto_index(int max_index);
HDCAM dcamcon_opencam(int cam_num);

void  dcamcon_show_dcamdev_info(HDCAM hdcam);

BOOL console_prompt(const char *prompt, char *buf, int32 bufsize);
void output_data(const char *filename, char *buf, int32 bufsize);

void toggle_readable_all_aslenum_devices(BOOL enable);
void enable_one_aslenum_device(int index);

// Note: DCAMERR SUCCESS is 1

#define CHECK_DCAM_ERR_RETURN(CALL, camera, ret)                               \
    {                                                                          \
        DCAMERR err = CALL;                                                    \
        if (err != 1)                                                          \
        {                                                                      \
            dcamcon_show_dcamerr(camera, err, "");                             \
            dcamdev_close(camera);                                             \
            dcamapi_uninit();                                                  \
                                                                               \
            printf("PROGRAM END\n");                                           \
            return 1;                                                          \
        }                                                                      \
    }

#define CHECK_DCAM_ERR_EXIT(CALL, camera, ret)                                 \
    {                                                                          \
        DCAMERR err = CALL;                                                    \
        if (err != 1)                                                          \
        {                                                                      \
            dcamcon_show_dcamerr(camera, err, "");                             \
            dcamdev_close(camera);                                             \
            dcamapi_uninit();                                                  \
                                                                               \
            printf("PROGRAM END\n");                                           \
            exit(1);                                                           \
        }                                                                      \
    }

#define CHECK_DCAM_ERR_PRINT(CALL, camera)                                     \
    {                                                                          \
        DCAMERR err = CALL;                                                    \
        if (err != 1)                                                          \
        {                                                                      \
            dcamcon_show_dcamerr(camera, err, "");                             \
        }                                                                      \
    }
