# requires pyvisa version 1.3, can be found at https://pypi.python.org/pypi/PyVISA/1.3
from visa import GpibInstrument
from pyvisa.visa_exceptions import VisaIOError
from math import sqrt, ceil
import os.path
import time

DEFAULT_TIME_STEP = 0.1  # in seconds
DEFAULT_NUM_POINTS = 1  # number of data points to collect for each measurement
DEFAULT_ROW_FORMAT_HEADER = "{:^14}{:^14}{:^15}{:^10}{:^8}"
DEFAULT_ROW_FORMAT_DATA = "{:< 14.6e}{:< 14.6e}{:< 15}{:<10.7}{:<8}"
DEFAULT_SAVE_PATH = "C://Data/pythonData/",


# useful to break up dataAll
def chunks(l, n):
    return [l[i:i + n] for i in range(0, len(l), n)]


class Keithley2400(GpibInstrument):
    """A class to interface with the Keithley 2400 sourcemeter"""

    def __init__(self, GPIBaddr):
        try:
            # call the visa.GpibInstrument init method w/ appropriate argument
            super(Keithley2400, self).__init__("GPIB::%d" % GPIBaddr)
            self._initialize()
            self._clearData()
            self.saveCounter = 0
        except VisaIOError:
            print('VisaIOError - is the keithley turned on?')

    #####################################################################################################
    # Internal methods: these are used internally but shouldn't be necessary for basic use of the class #
    #####################################################################################################

    # do setup stuff I don't really understand
    # adapted from http://pyvisa.sourceforge.net/pyvisa.html#a-more-complex-example
    def _initialize(self):
        self.write("*CLS")
        self.write("STATUS:MEASUREMENT:ENABLE 512")
        self.write("*SRE 1")
        self.write("ARM:COUNT 1")
        self.write("ARM:SOURCE BUS")
        self.write("TRACE:FEED SENSE1")

        # set various things to default values
        self.setDelay()
        self.setNumPoints()

    # clear the saved data from previous measurement
    def _clearData(self):
        self.dataAll = []
        self.dataVolt = []
        self.dataCurr = []
        self.dataRes = []
        self.dataTime = []

    # start a measurement and wait for the 'measurement is done' signal from the Keithley
    def _startMeasurement(self):
        self._startNoWait()
        self._catchSRQ()

    # start a measurement
    def _startNoWait(self):
        self.write("OUTPUT ON")
        self.write("TRACE:FEED:CONTROL NEXT")
        self.write("INIT")
        self.trigger()

    # catch the 'measurement is done' signal from the Keithely
    def _catchSRQ(self):
        self.wait_for_srq(None)
        self.ask("STATUS:MEASUREMENT?")

    # pull data from the Keithley
    # always call this before _stopMeasurement() bc _stopMeasurement clears the keithley's buffer
    def _pullData(self):
        # returns (V, I, I/V, time, ?) for each data point
        # (at least when measuring resistance)
        # when not measuring resistance, I/V column = 9.91e37
        self.dataTemp = self.ask_for_values("TRACE:DATA?")

        self.dataAll += self.dataTemp
        self.dataVolt += self.dataTemp[0::5]
        self.dataCurr += self.dataTemp[1::5]
        self.dataRes += self.dataTemp[2::5]
        self.dataTime += self.dataTemp[3::5]

        # self.write("TRACE:CLEAR")

    # stop a measurement, turn output off
    def _stopMeasurement(self):
        self.write("OUTPUT OFF")
        self.write("TRACE:CLEAR")
        self.ask("STATUS:MEASUREMENT?")

    ##############################################################
    # Configuration methods: use these to configure the Keithley #
    ##############################################################

    # set the number of data points to take
    def setNumPoints(self, numPts=DEFAULT_NUM_POINTS):
        self.write("TRIGGER:COUNT %d" % numPts)
        self.write("TRACE:POINTS %d" % numPts)

    # set the delay between data points (in sec)
    def setDelay(self, delay=DEFAULT_TIME_STEP):
        self.write("TRIGGER:DELAY %f" % delay)

    # set DC source, expects source to be either "voltage" or "current"
    def setSourceDC(self, source, value):
        # if (self.getMeasure()=='RES'):
        #   self.write("SENSE:RESISTANCE:MODE MANUAL")
        if source.lower() == "voltage":
            self.write("SOURCE:FUNCTION:MODE VOLTAGE")
            self.write("SOURCE:VOLTAGE:MODE FIXED")
            self.write("SOURCE:VOLTAGE:RANGE " + str(value))
            self.write("SOURCE:VOLTAGE:LEVEL " + str(value))
        elif source.lower() == "current":
            self.write("SOURCE:FUNCTION:MODE CURRENT")
            self.write("SOURCE:CURRENT:MODE FIXED")
            self.write("SOURCE:CURRENT:RANGE " + str(value))
            self.write("SOURCE:CURRENT:LEVEL " + str(value))

    # set sweep source, expects source to be either "voltage" or "current"
    def setSourceSweep(self, source, startValue, stopValue, sourceStep, timeStep=DEFAULT_TIME_STEP):
        numPts = ceil(abs((stopValue - startValue) / sourceStep)) + 1
        if self.getMeasure() == 'RES':
            self.write("SENSE:RESISTANCE:MODE MANUAL")
        if source.lower() == "voltage":
            self.write("SOURCE:FUNCTION:MODE VOLTAGE")
            self.write("SOURCE:VOLTAGE:MODE SWEEP")
            # self.write("SOURCE:VOLTAGE:RANGE " + str(stopValue))
            self.write("SOURCE:VOLTAGE:START " + str(startValue))
            self.write("SOURCE:VOLTAGE:STOP " + str(stopValue))
            self.write("SOURCE:VOLTAGE:STEP " + str(sourceStep))
            self.setNumPoints(numPts)
            self.setDelay(timeStep)
        elif source.lower() == "current":
            self.write("SOURCE:FUNCTION:MODE CURRENT")
            self.write("SOURCE:CURRENT:MODE SWEEP")
            self.write("SOURCE:CURRENT:RANGE " + str(stopValue))
            self.write("SOURCE:CURRENT:START " + str(startValue))
            self.write("SOURCE:CURRENT:STOP " + str(stopValue))
            self.write("SOURCE:CURRENT:STEP " + str(sourceStep))
            self.setNumPoints(numPts)
            self.setDelay(timeStep)
        else:
            print("Error: bad arguments")
        return numPts

    # set what is being measured (VOLTage or CURRent or RESistance)
    def setMeasure(self, measure):
        self.write("SENSE:FUNCTION:OFF 'CURR:DC', 'VOLT:DC', 'RES'")
        if measure.lower() == "voltage":
            self.write("SENSE:FUNCTION:ON 'VOLTAGE:DC'")
        elif measure.lower() == "current":
            self.write("SENSE:FUNCTION:ON 'CURRENT:DC'")
        elif measure.lower() == "resistance":
            self.write("SENSE:FUNCTION:ON 'CURRENT:DC'")
            self.write("SENSE:FUNCTION:ON 'RESISTANCE'")
        else:
            print("Expected one of [current, voltage, or resistance]")

    # set the upper limit for how much current / voltage will be sourced
    def setCompliance(self, source, limit):
        if source.lower() == 'voltage':
            self.write("SENS:VOLT:PROT " + str(limit))
        if source.lower() == 'current':
            self.write("SENS:CURR:PROT " + str(limit))
        else:
            print("Expected one of [current, voltage]")

    # set resistance measurements to 4-wire
    def setFourWire(self):
        if self.ask("SENSE:FUNCTION?").split(",")[-1].strip('"') == 'RES':
            self.write("SYSTEM:RSENSE ON")
            print('Resistance measurement changed to 4-wire')
        else:
            print('Must be measuring resistance')

    # set resistance measurements to 2-wire
    def setTwoWire(self):
        if self.ask("SENSE:FUNCTION?").split(",")[-1].strip('"') == 'RES':
            self.write("SYSTEM:RSENSE OFF")
            print('Resistance measurement changed to 2-wire')
        else:
            print('Must be measuring resistance')

    # set triggering to use TLINK connections (for fastest linking of two Keithleys)
    def setTLINK(self, inputTrigs, outputTrigs):
        self.write("TRIG:SOURCE TLINK")
        self.write("TRIG:INPUT {}".format(inputTrigs))
        self.write("TRIG:OUTPUT {}".format(outputTrigs))

    # set triggering to be immediate (default for single Keithley measurements)
    def setNoTLINK(self):
        self.write("TRIG:SOURCE IMMEDIATE")
        self.write("TRIG:INPUT NONE")
        self.write("TRIG:OUTPUT NONE")

    # get what is being measured (VOLTage or CURRent or RESistance)
    def getMeasure(self):
        # keithley returns something like ' "VOLT:DC", "RES" ' or ' "CURR:DC" '
        return self.ask("SENSE:FUNCTION?").split(",")[-1].strip('"')

    # get what is being sourced (VOLTage or CURRent)
    # returns ['VOLTAGE'|'CURRENT', value in volts|amps]
    def getSource(self):
        source = self.ask("SOURCE:FUNCTION:MODE?")
        if source == "VOLT":
            # sourceMode = self.ask("SOURCE:VOLTAGE:MODE?")
            return ['VOLTAGE', self.ask_for_values("SOURCE:VOLTAGE:LEVEL?")[0]]
        elif source == "CURR":
            return ['CURRENT', self.ask_for_values("SOURCE:CURRENT:LEVEL?")[0]]

    ########################################################
    # Operation methods: use these to operate the Keithley #
    ########################################################

    # perform a measurement w/ current parameters
    def doMeasurement(self):
        self._clearData()
        self._startMeasurement()
        self._pullData()
        self._stopMeasurement()

    # ramp the output from rampStart to rampTarget
    def rampOutput(self, rampStart, rampTarget, step, timeStep=50E-3):
        if rampTarget < rampStart: step = -abs(step)
        if rampTarget > rampStart: step = abs(step)

        source = self.getSource()[0]  # either 'voltage' or 'current'
        sourceValue = rampStart
        self.setSourceDC(source, sourceValue)
        self.write("OUTPUT ON")
        # hack-y : while (current level + step) is closer to target than current level
        while abs((sourceValue + step) - rampTarget) <= abs(sourceValue - rampTarget):
            sourceValue += step
            self.setSourceDC(source, sourceValue)
            time.sleep(timeStep)
        return sourceValue

    # starting with the output off, turn the output on then ramp the output up/down to a specified level
    def rampOutputOn(self, rampTarget, step, timeStep=50E-3):
        rampStart = 0
        sourceValue = self.rampOutput(rampStart, rampTarget, step, timeStep)
        return sourceValue

    # starting with the output on, ramp the output to 0, then turn the output off
    def rampOutputOff(self, rampStart, step, timeStep=50E-3):
        rampTarget = 0
        sourceValue = self.rampOutput(rampStart, rampTarget, step, timeStep)
        self.write("OUTPUT OFF")
        return sourceValue

    # save the collected data to file
    # mode 'a' appends to existing file, mode 'i' increments file counter ie test0001.txt, test0002,txt
    def saveData(self, filePath=DEFAULT_SAVE_PATH, fileName="test.txt", mode='i'):
        if filePath[-1] != '/': filePath += '/'
        if fileName[-4:] != '.txt': fileName += '.txt'

        if mode == 'a':
            saveFile = open(filePath + fileName, "a+")
        elif mode == "i":
            self.saveCounter = 0
            while True:
                self.saveCounter += 1
                # print("checking file: " + filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".txt")
                # print("")
                if not os.path.exists(filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".txt"):
                    break
            saveFile = open(filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".txt", "a+")
        else:
            print("invalid mode")
            return -1

        saveFile.write("\n")
        # single line format
        # saveFile.write(DEFAULT_ROW_FORMAT_HEADER.format("V (volts)","I (amps)","I/V (ohms)","t (s)","?"))

        # format for importing to Origin
        saveFile.write(DEFAULT_ROW_FORMAT_HEADER.format("V", "I", "I/V", "t", "?"))
        saveFile.write("\n")
        saveFile.write(DEFAULT_ROW_FORMAT_HEADER.format("volts", "amps", "ohms", "s", "?"))
        saveFile.write("\n")
        for row in chunks(self.dataAll, 5):
            saveFile.write(DEFAULT_ROW_FORMAT_DATA.format(*row))
            saveFile.write("\n")
        saveFile.close()
	return saveFile.name

    def printSummary(self):
        print("Measuring: " + self.getMeasure())
        print("Sourcing: " + str(self.getSource()))
        print("")
        print(DEFAULT_ROW_FORMAT_HEADER.format("V (volts)", "I (amps)", "I/V (ohms)", "t (s)", "?"))
        for row in chunks(self.dataAll, 5):
            print(DEFAULT_ROW_FORMAT_DATA.format(*row))
        print("")
