#!/usr/bin/python
#
#
#
#


from ctypes import cdll

from ctypes import byref, POINTER, create_string_buffer, sizeof, c_float, \
    c_int16, c_int32, c_uint32, c_void_p, cast

from ctypes import c_int16 as c_enum

import time
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
)

# sampling method
#BM_BLOCK (0) Collect a single block and stop
#BM_WINDOW (1) Collect a sequence of overlapping blocks
#BM_STREAM (2) Collect a continuous stream of data
(BM_BLOCK,
BM_WINDOW,
BM_STREAM) = map(c_enum, xrange(3))

# Reading Type
# HRDL_DIFFERENTIAL (0) differential reading
# HRDL_SINGLE (1) single ended reading
(HRDL_DIFFERENTIAL,
HRDL_SINGLE) = map(c_enum, xrange(2))

# Conversion times
# HRDL_60MS (0) 60 ms
# HRDL_100MS (1) 100 ms
# HRDL_180MS (2) 180 ms
# HRDL_340MS (3) 340 ms
# HRDL_660MS (4) 660 ms
(HRDL_60MS,
HRDL_100MS,
HRDL_180MS,
HRDL_340MS,
HRDL_660MS) = map(c_enum, xrange(5))

# ADC Voltage ranges
# HRDL_2500_MV (0) +-2500 mV ADC-20 and ADC-24
# HRDL_1250_MV (1) +-1250 mV ADC-20 and ADC-24
# HRDL_625_MV (2) +-625 mV ADC-24 only
# HRDL_313_MV (3) +-312.5 mV ADC-24 only
# HRDL_156_MV (4) +-156.25 mV ADC-24 only
# HRDL_78_MV (5) +-78.125 mV ADC-24 only
# HRDL_39_MV (6) +-39.0625 mV ADC-24 only
(HRDL_2500_MV,
HRDL_1250_MV,
HRDL_625_MV,
HRDL_313_MV,
HRDL_156_MV,
HRDL_78_MV,
HRDL_39_MV) = map(c_enum, xrange(7))

# Information polling from driver
# HRDL_DRIVER_VERSION (0) The version of PicoHRDL.dll
# HRDL_USB_VERSION (1) The type of USB to which the unit is connected
# HRDL_HARDWARE_VERSION (2) The hardware version of the HRDL
# HRDL_VARIANT_INFO (3) Information about the type of HRDL
# HRDL_BATCH_AND_SERIAL (4) Batch and serial numbers of the unit CMY02/116
# HRDL_CAL_DATE (5) Calibration date of the unit
# HRDL_KERNEL_DRIVER_VERSION (6) Kernel driver version
# HRDL_ERROR (7) One of the error codes listed in device error method
# HRDL_SETTINGS_ERROR (8) One of the error codes listed in settings error method
(HRDL_DRIVER_VERSION,
HRDL_USB_VERSION,
HRDL_HARDWARE_VERSION,
HRDL_VARIANT_INFO,
HRDL_BATCH_AND_SERIAL,
HRDL_CAL_DATE,
HRDL_KERNEL_DRIVER_VERSION,
HRDL_ERROR,
HRDL_SETTINGS_ERROR) = map(c_enum, xrange(9))

class ADCError(Exception):
    """Exceptions raised for this module."""

    def __init__(self, message):
        self.message = message

# 
class ADC():

    """
        The following class is a ctypes wrapper around libpicohrdl the picotech library to 
        access the ADC-20 and ADC-24 data loggers

    """

    def __init__(self, serialNumber=None, connect=True):

        self.logger = logging.getLogger('ADC')

        self.logger.debug('Initing ADC module')

        self.lib = cdll.LoadLibrary("libpicohrdl.so")

        # our device handle
        self.handle = None

        self.max_channels = 0
        self.adc_bits = 1

        # convert readings to voltages
        self.convert_readings = False

        self.info_buffer = create_string_buffer(80)

        return

    def open(self):

        """
            Open the DAQ and pulls back a little info

        """

        self.logger.debug('Probing for DAQ Device' )

        device = self.lib.HRDLOpenUnit()

        if( device > 0 ):

            #
            result = self.lib.HRDLGetUnitInfo(device, self.info_buffer, sizeof(self.info_buffer), HRDL_BATCH_AND_SERIAL);

            (self.batch, self.serial) = self.info_buffer.value.split('/')

            self.logger.debug('Device info batch:%s, serial:%s' % (self.batch, self.serial) )

            result = self.lib.HRDLGetUnitInfo(device, self.info_buffer, sizeof(self.info_buffer), HRDL_VARIANT_INFO);

            self.adc_type = int( self.info_buffer.value )

            self.handle = device

            # setup some device specific vars
            self.max_channels = 8 if self.adc_type == 20 else 16
            self.adc_bits = 20 if self.adc_type == 20 else 24

            self.logger.info('Found ADC%d Device' % self.adc_type )

        else:
            raise ADCError('Unable to find DAQ device')

        return

    def close(self):

        """
            Close the DAQ

        """
        if not self.handle is None:

            status = self.lib.HRDLCloseUnit( self.handle )

            if status:

                self.logger.info('Closed DAQ Device')

            else:

                self.logger.error("Error closing DAQ device")

            self.handle = None

        return

    def convert_to_millivolts(self, convert = True):

        """
            Scale the output of the DAQ into the appriorate Millivolt range

        """

        self.logger.debug('Enabling millivolt conversion')

        if convert:
            self.convert_readings = True

        return

    def enabled_channel_count(self):

        """
            This function returns the number of enabled analog channels

        """
    
        if self.handle: 

            self.logger.debug('Getting number of enabled channels')

            channel_count = c_int16(0)

            result = self.lib.HRDLGetNumberOfEnabledChannels(self.handle, byref(channel_count))

            if not result:

                self.logger.error('Error getting enabled channel count')

            else:

                return channel_count.value

        return

    def run(self, samples, method):

        """
            This function starts the device sampling and storing the samples in the driver's buffer.

        """

        if self.handle:

            self.logger.debug('Collecting %d samples from enabled channels' % samples)

            assert type(method) is c_int16

            result = self.lib.HRDLRun(self.handle, c_int32(samples), method)

            if not result:

                self.logger.error('Error starting sample collection')
                self._get_settings_error()

        return

    def isready(self, maxsleepms = 1000):

        """
            This function indicates when the readings are ready to be retrieved from the driver.

        """

        if self.handle:

            self.logger.debug('Polling for DAQ readiness')

            ready = True

            start = time.time()

            while ready:
           
                result = self.lib.HRDLReady(self.handle)

                if result:

                    self.logger.debug('Device status ready')

                    return True

                else:

                    difference = ( time.time() - start ) * 1000

                    if difference > maxsleepms:

                        self.logger.debug('Device did not become ready')

                        ready = False

                # 
                time.sleep(0.01)

        return False

    def values(self, samples, active_channels):

        """
            This function returns the requested number of samples for each enabled channel.

        """

        if self.handle:

            self.logger.debug('Collecting %d samples from enabled channels' % samples)

            value_count = samples * active_channels

            values = ( c_int32 * value_count )()

            overflow = c_int16(0)

            result = self.lib.HRDLGetValues(self.handle, cast(values,POINTER(c_int32)), byref(overflow), samples)

            if not result:

                self.logger.error('Error starting sample collection')
                self._get_settings_error()

            else:

                self.logger.debug('%d readings returned' % result)

                if overflow.value:

                    #
                    self.logger.warning('Recieved overflow reading from channel %d' % channel)

                # 
                return values

        return

    def times_and_values(self, samples, active_channels):

        """
            This function returns the requested number of samples for each enabled channel and
            the times when the samples were taken.

        """

        if self.handle:

            self.logger.debug('Collecting %d samples from enabled channels' % samples)

            value_count = samples * active_channels

            values = ( c_int32 * value_count )()

            times = ( c_int32 * value_count )()

            overflow = c_int16(0)

            result = self.lib.HRDLGetTimesAndValues(self.handle, cast(times,POINTER(c_int32)), cast(values,POINTER(c_int32)), byref(overflow), samples)

            if not result:

                self.logger.error('Error starting sample collection')
                self._get_settings_error()

            else:

                self.logger.debug('%d readings returned' % result)

                if overflow.value:

                    #
                    self.logger.warning('Recieved overflow reading from channel %d' % channel)

                #
                return (times, values)

        return

    def sample_interval(self, sample_interval, conversion_time):

        """
            This sets the sampling time interval. The number of channels active must be able to
            convert within the specified interval.

        """

        self.logger.debug('Setting sampling interval')

        # Time interval in milliseconds within which all conversions must
        # take place before the next set of conversions starts.
        c_sample_interval = c_int32(sample_interval)
   
        #
        assert type(conversion_time) is c_int16

        result = self.lib.HRDLSetInterval(self.handle, sample_interval, conversion_time)

        if not result:

            self.logger.error('Error setting sampling time')
            self._get_settings_error()

        return

    def mains_noise_filter(self):

        """
            This function configures the mains noise rejection setting. Rejection takes effect the
            next time sampling occurs.

        """

        self.logger.debug('Enabling mains noise filter')

        # Specifies whether 50 Hz or 60 Hz noise rejection is applied.
        # 0: reject 50Hz
        # <> 0: reject 60 Hz
        noise_type = c_int16(0)

        result = self.lib.HRDLSetMains(self.handle, noise_type)

        if not result:

            self.logger.error('Error setting DAQ noise filter')

        return

    def stop(self):

        """
            This function stops the device when streaming.

        """

        self.logger.debug('Stopping sample streaming')

        self.lib.HRDLStop(self.handle)

        return

    def reset_analog_channels(self):

        """
            Reset all analog channel to the default single-ended, 2500mV, disabled

        """

        self.logger.debug('Resetting all channels')

        for channel in range(1, self.max_channels + 1):

            self.set_analog_channel( CHANNEL, HRDL_SINGLE, HRDL_2500_MV, False )

        return

    def set_analog_channel(self, channel, reading_type, voltage_range, enabled):

        """
            Enable a analog channel to specified settings

        """

        if channel < self.max_channels + 1:

            self.logger.debug('Setting up channel %d' % channel)

            assert type(reading_type) is c_int16
            assert type(voltage_range) is c_int16

            # 0: dormant, <> 0: active
            c_enabled = c_int16(enabled)

            result = self.lib.HRDLSetAnalogInChannel(self.handle, c_int16(channel), c_enabled, voltage_range, reading_type)

            if not result:

                self.logger.error('Error setting up channel %d' % channel)
                self._get_settings_error()

        else:

            self.logger.error('Nonsense channel number %d' % channel)

    
        return


    def _get_device_error(self):

        """
            Pulls back a more specific device error - doesn't seem to work (poor linux driver maybe)

        """

        # Error codes (when info = HRDL_ERROR) 
        ERROR_CODES = {
            0x00 : ["HRDL_OK", "The unit is functioning correctly"],
            0x01 : ["HRDL_KERNEL_DRIVER", "The picopp.sys file is to old to support this product"],
            0x02 : ["HRDL_NOT_FOUND", "No data logger could be found"],
            0x03 : ["HRDL_CONFIG_FAIL", "Unable to download firmware"],
            0x04 : ["HRDL_ERROR_OS_NOT_SUPPORTED", "The operating system is not supported by this device"],
            0x05 : ["HRDL_MAX_DEVICES", "The maximum number of units allowed are already open"],
        }

        if self.handle:

            result = self.lib.HRDLGetUnitInfo(self.handle, self.info_buffer, sizeof(self.info_buffer), HRDL_ERROR);

            code = int(self.info_buffer.value)

            if code in ERROR_CODES:

                self.logger.error("BROKEN: Device error: %s : %s" % ( ERROR_CODES[code][0], ERROR_CODES[code][1]))

        return

    def _get_settings_error(self):

        """
            Pulls back a more specific settings error

        """

        # Settings Error Codes (when info = HRDL_SETTINGS_ERROR)

        SETTING_ERROR_CODES = {
            0x00 : ["SE_CONVERSION_TIME_OUT_OF_RANGE", "The conversion time parameter is out of range"],
            0x01 : ["SE_SAMPLEINTERVAL_OUT_OF_RANGE", "The sample time interval is out of range"],
            0x02 : ["SE_CONVERSION_TIME_TOO_SLOW", "The conversion time chosen is not fast enough to convert all channels within the sample interval"],
            0x03 : ["SE_CHANNEL_NOT_AVAILABLE", "The channel being set is valid but not currently available"],
            0x04 : ["SE_INVALID_CHANNEL", "The channel being set is not valid for this device"],
            0x05 : ["SE_INVALID_VOLTAGE_RANGE", "The voltage range being set for this device is not valid"],
            0x06 : ["SE_INVALID_PARAMETER", "One or more parameters are invalid"],
            0x07 : ["SE_CONVERSION_IN_PROGRESS", "A conversion is in progress for a single asynchronous operation"],
            0x08 : ["SE_OK", "All settings have been completed successfully"],
        }

        if self.handle:

            result = self.lib.HRDLGetUnitInfo(self.handle, self.info_buffer, sizeof(self.info_buffer), HRDL_SETTINGS_ERROR);

            code = int(self.info_buffer.value)

            if code in SETTING_ERROR_CODES:

                self.logger.error("Device error: %s : %s" % ( SETTING_ERROR_CODES[code][0], SETTING_ERROR_CODES[code][1]))
            else:
                self.logger.error("Unknown Device error: %d" % code)

        return
   

    def get_single_value(self, channel, voltage_range, conversion_time, reading_type):

        """
            This function takes one sample for the specified channel at the selected voltage range
            and conversion time.
        """

        if self.handle and channel < self.max_channels + 1:


            self.logger.debug('Getting value from channel %d' % channel)

            assert type(reading_type) is c_int16
            assert type(conversion_time) is c_int16
            assert type(voltage_range) is c_int16

            overflow = c_int16(0)
            value    = c_int32(0)

            result = self.lib.HRDLGetSingleValue(self.handle, c_int16(channel), voltage_range, conversion_time, reading_type, byref(overflow), byref(value))

            if not result:

                self.logger.error('Error getting value from channel %d' % channel)
                self._get_settings_error()

            else:

                if overflow.value:

                    #
                    self.logger.warning('Recieved overflow reading from channel %d' % channel)
  
                return self._convert_reading( value.value, voltage_range, channel )

        return

    def start_single_value_async(self, channel, voltage_range, conversion_time, reading_type):

        """
            This function starts the unit sampling one value without blocking the calling
            application's flow.
        """

        if self.handle and channel < self.max_channels + 1:

            self.logger.debug('Start async value poll from channel %d' % channel)

            assert type(reading_type) is c_int16
            assert type(conversion_time) is c_int16
            assert type(voltage_range) is c_int16

            result = self.lib.HRDLCollectSingleValueAsync(self.handle, c_int16(channel), voltage_range, conversion_time, reading_type )

            if not result:

                self.logger.error('Error initiating collection from channel %d' % channel)
                self._get_settings_error()

        return

    def finish_single_value_async(self, channel, voltage_range ):

        """
            This function completes the unit sampling one value without blocking the calling
            application's flow.
        """

        if self.handle and channel < self.max_channels + 1:

            self.logger.debug('Completing async value poll from channel %d' % channel)

            assert type(voltage_range) is c_int16

            overflow = c_int16(0)
            value    = c_int32(0)

            result = self.lib.HRDLGetSingleValueAsync(self.handle, byref(value), byref(overflow) )

            if not result:

                self.logger.error('Error getting async value from channel %d' % channel)
                self._get_settings_error()

            else:

                if overflow.value:

                    #
                    self.logger.warning('Recieved overflow reading from channel %d' % channel)
 
                return self._convert_reading( value.value, voltage_range, channel )

        return


    def _convert_reading(self, reading, voltage_range, channel):

        """
        """

        if not self.convert_readings:
            return reading

        if self.handle and channel < self.max_channels + 1:

            min_adc    = c_int32(0) # minimum ADC count available
            max_adc    = c_int32(0) # maximum ADC count available

            result = self.lib.HRDLGetMinMaxAdcCounts( self.handle, byref(min_adc), byref(max_adc), c_int16(channel) )

            if not result:

                self.logger.error('Error getting min/max counts from channel %d' % channel)
                self._get_settings_error()

            else:

                if min_adc.value <= reading <= max_adc.value:

                    max_voltage = 2500 / ( 2 ** voltage_range.value )

                    voltage_step = ( max_voltage * 1.0 ) / max_adc.value

                    value = ( reading * voltage_step )

                    return value

                else:

                    self.logger.error('Error reading %d seems to be out of range for channel %d' % (reading, channel) )

        return
 
    def __del__(self):

        self.close()

if __name__ == "__main__":

    CHANNEL = 1 
  
    SAMPLE_COUNT = 10
    SAMPLE_INTERVAL = 700
 
    SYNC_TEST = 0
    ASYNC_TEST = 1
    MULTIVALUE_TEST = 0
    MULTIVALUETIME_TEST = 1

    logger = logging.getLogger()
 
    daq = ADC()

    # init device
    daq.open()
    daq.mains_noise_filter()
    daq.convert_to_millivolts()
    daq.reset_analog_channels()

    if MULTIVALUE_TEST:

      logger.info("Multi Value Test")

      daq.sample_interval( SAMPLE_INTERVAL, HRDL_660MS )

      daq.set_analog_channel( CHANNEL, HRDL_SINGLE, HRDL_2500_MV, True )

      count = daq.enabled_channel_count()

      if count is not None :

        logger.info("MULTICHANNEL_TEST Enabled Channels: %d" % count)
 
        daq.run(SAMPLE_COUNT, BM_BLOCK)

        logger.info("MULTICHANNEL_TEST Sleeping")

        time.sleep( (SAMPLE_INTERVAL / 1000.0) * SAMPLE_COUNT)

        daq.isready()

        values = daq.values(SAMPLE_COUNT, count)

        for inx, value in enumerate(values):
          logger.info("MULTICHANNEL_TEST Value #%d (mV): %0.3f" % (inx, daq._convert_reading(value, HRDL_2500_MV, CHANNEL)))

        daq.stop()

    if MULTIVALUETIME_TEST:

      logger.info("Multi Value + Time Test")

      daq.sample_interval( SAMPLE_INTERVAL, HRDL_660MS )

      daq.set_analog_channel( CHANNEL, HRDL_SINGLE, HRDL_1250_MV, True )

      count = daq.enabled_channel_count()

      if count is not None :

        logger.info("MULTIVALUETIME_TEST Enabled Channels: %d" % count)

        # sliding windows this time
        daq.run(SAMPLE_COUNT, BM_WINDOW)

        logger.info("MULTIVALUETIME_TEST Sleeping")

        time.sleep( (SAMPLE_INTERVAL / 1000.0) * SAMPLE_COUNT ) 

        daq.isready()

        (times, values) = daq.times_and_values(SAMPLE_COUNT, count)

        for inx, value in enumerate(values):
           logger.info("MULTIVALUETIME_TEST Time: %d , Value #%d (mV): %0.3f" % (times[inx], inx, daq._convert_reading(value, HRDL_1250_MV, CHANNEL)))

        logger.info("MULTIVALUETIME_TEST Sleeping")

        time.sleep( (SAMPLE_INTERVAL / 1000.0) * SAMPLE_COUNT )                              

        daq.isready()

        (times, values) = daq.times_and_values(SAMPLE_COUNT, count)

        for inx, value in enumerate(values):
           logger.info("MULTIVALUETIME_TEST Time: %d , Value #%d (mV): %0.3f" % (times[inx], inx, daq._convert_reading(value, HRDL_1250_MV, CHANNEL)))

        daq.stop()

    if SYNC_TEST:

      logger.info("SYNC Test")

      value = daq.get_single_value( CHANNEL, HRDL_2500_MV , HRDL_660MS , HRDL_SINGLE )

      if value:
        logger.info("SYNC_TEST Value (mV): %0.3f" % value)

    if ASYNC_TEST:

      logger.info("ASYNC Test")

      daq.start_single_value_async( CHANNEL, HRDL_1250_MV , HRDL_660MS , HRDL_SINGLE )

      while not daq.isready(maxsleepms=10):
        logger.info("ASYNC_TEST Polling for result")
        time.sleep(1)

      value = daq.finish_single_value_async( CHANNEL, HRDL_1250_MV )

      if value:
        logger.info("ASYNC_TEST Value (mV): %0.3f" % value)

    # close device
    daq.close()

    del(daq)
