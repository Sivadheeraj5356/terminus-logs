#ifndef AC_LIMITS_H
#define AC_LIMITS_H

#define AC_NX 48
#define AC_NY 24
#define AC_DX 0.01
#define AC_DT 3.0e-6
#define AC_STEPS 8192
#define AC_RECORD_STRIDE 4
#define AC_MAX_SAMPLES (AC_STEPS / AC_RECORD_STRIDE)
#define AC_SR_HZ 83333
#define AC_BRIDGE_X 36
#define AC_BRIDGE_Y 12
#define AC_MIC_X 42
#define AC_MIC_Y 12
#define AC_C_AIR 343.0
#define AC_C_WOOD 1200.0
#define AC_MAX_PROFILE 64
#define AC_MAX_FORMANTS 4
#define AC_FORMANT_MIN_HZ 180.0
#define AC_FORMANT_MAX_HZ 3500.0
#define AC_PEAK_MIN_DB 6.0
#define AC_PEAK_MIN_SEP_HZ 40.0

#endif
