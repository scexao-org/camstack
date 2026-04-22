Point Grey Research Blackfly BFLY-U3-13S2M
==========================================

*Version: FW:v1.8.3.00 FPGA:v2.02*

Attributes
----------

`AcquisitionFrameRate` : `float`
  Controls the acquisition rate (in Hertz) at which the frames are captured.
  - default access: read only
  - default value: `33.999977111816406`
  - unit: Hz
  - default range: 1.0 - 34.33476257324219

`AcquisitionFrameRateAuto` : `enum`
  Controls the mode for automatic frame rate adjustment.
  - default access: read only
  - default value: `'Off'`
  - possible values: `'Off'`, `'Once'`, `'Continuous'`

`AcquisitionFrameRateEnabled` : `bool`
  Enables manual control of the camera frame rate.
  - default access: read/write
  - default value: `False`

`AcquisitionMode` : `enum`
  Sets the acquisition mode of the device.
  - default access: read/write
  - default value: `'Continuous'`
  - possible values: `'Continuous'`, `'SingleFrame'`, `'MultiFrame'`

`BinningHorizontal` : `int`
  Number of horizontal pixels to combine together.
  - default access: read only
  - default value: `1`
  - default range: 1 - 4

`BinningVertical` : `int`
  Number of vertical pixels to combine together.
  - default access: read/write
  - default value: `1`
  - default range: 1 - 4

`DeviceFamilyName` : `string`
  Family name of the device.
  - default access: read only
  - default value: `'GEN2-USB'`

`DeviceID` : `string`
  Device identifier (serial number).
  - default access: read only
  - default value: `'17175549'`

`DeviceModelName` : `string`
  Model name of the device.
  - default access: read only
  - default value: `'Blackfly BFLY-U3-13S2M'`

`DeviceTemperature` : `float`
  Device temperature in degrees Celcius (C).
  - default access: read only
  - default value: `45.150000000000034`
  - unit: °C
  - default range: -1.7976931348623157e+308 - 1.7976931348623157e+308

`ExposureAuto` : `enum`
  Sets the automatic exposure mode when Exposure Mode is Timed.
  - default access: read/write
  - default value: `'Off'`
  - possible values:
    - `'Off'`: Exposure set to manual control.
    - `'Once'`: Exposure is automatically adjusted once, then returns to Off.
    - `'Continuous'`: Exposure is automatically adjusted by the camera

`ExposureMode` : `enum`
  Sets the operation mode of the Exposure (or shutter).
  - default access: read/write
  - default value: `'Timed'`
  - possible values: `'Timed'`, `'TriggerWidth'`

`ExposureTime` : `float`
  Exposure time in microseconds when Exposure Mode is Timed and ExposureAuto is Off.
  - default access: read/write
  - default value: `20009.636878967285`
  - unit: us
  - default range: 45.59755325317383 - 31983741.760253906

`ExposureTimeAbs` : `float`
  Exposure time in microseconds when Exposure Mode is Timed and ExposureAuto is Off.
  - default access: read/write
  - default value: `20009.636878967285`
  - unit: us
  - default range: 45.59755325317383 - 31983741.760253906

`Fmt7RegBaseAddress` : `int`
  - default access: read only
  - default value: `281474724006400`
  - default range: -9223372036854775808 - 9223372036854775807

`Gain` : `float`
  Gain applied to the image in dB.
  - default access: read/write
  - default value: `0.0`
  - unit: dB
  - default range: 0.0 - 23.99051856994629

`GainAuto` : `enum`
  Sets the automatic gain control (AGC) mode.
  - default access: read/write
  - default value: `'Off'`
  - possible values:
    - `'Off'`: Gain is User controlled using Gain.
    - `'Once'`: Gain is automatically adjusted once by the device. Once it has converged, it automatically returns to the Off state.
    - `'Continuous'`: Gain is constantly adjusted by the device.

`Height` : `int`
  Height of the image provided by the device (in pixels).
  - default access: read/write
  - default value: `340`
  - default range: 2 - 356

`HeightMax` : `int`
  Maximum height of the image (in pixels).
  - default access: read only
  - default value: `964`
  - default range: 0 - 65535

`OffsetX` : `int`
  Vertical offset from the origin to the AOI (in pixels).
  - default access: read/write
  - default value: `914`
  - default range: 0 - 916

`OffsetY` : `int`
  Horizontal offset from the origin to the AOI (in pixels).
  - default access: read/write
  - default value: `608`
  - default range: 0 - 624

`ParameterSelector` : `enum`
  Selects which parameter whose limit will be removed.
  - default access: read/write
  - default value: `'Gain'`
  - possible values: `'Gain'`

`Width` : `int`
  Width of the image provided by the device (in pixels).
  - default access: read/write
  - default value: `372`
  - default range: 4 - 372

`WidthMax` : `int`
  Maximum width of the image (in pixels).
  - default access: read only
  - default value: `1288`
  - default range: 0 - 65535

Commands
--------

**Note: the camera recording should be started/stopped using the `start` and `stop` methods, not any of the functions below (see simple_pyspin documentation).**

`AcquisitionStart()`:
  Starts the Acquisition of the device.
  - default access: write only

`AcquisitionStop()`:
  Stops the acquisition of the device at the end of the current frame.
  - default access: write only

`ActivePageSave()`:
  Save the data in the active page to the data flash.
  - default access: write only

`DeviceReset()`:
  This is a command that immediately resets and reboots the device.
  - default access: write only

`TimestampLatch()`:
  Latches the curretn device time into the timstamp register.
  - default access: write only

`TransmitFailureCountReset()`:
  Reset the transmit failure count.
  - default access: write only

`TriggerEventTest()`:
  This command sends a test event.
  - default access: write only

`TriggerSoftware()`:
  Generates an internal trigger if Trigger Source is set to Software.
  - default access: not available

`UserSetLoad()`:
  Loads the User Set specified by UserSetSelector to the device and makes it active.
  - default access: write only

`UserSetSave()`:
  Save the User Set specified by UserSetSelector to the non-volatile memory of the device.
  - default access: write only

`pgrCurrentCorrectedPixelSave()`:
  Save the Current Corrected Pixels to the non-volatile memory of the device.
  - default access: write only
