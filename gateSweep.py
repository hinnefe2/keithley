# example script using the Keithley2400 python class to do a gate sweep measurement (with two keithley 2400s)
# meant to be run interactively from the interpreter, i.e.
# >>> from gateSweep import gateSweep
# >>> gs = gateSweep()
# >>> gs.doSweep()

DEFAULT_SAVE_PATH = '/users/henry/pythonData/'
DEFAULT_SAVE_FILE = 'gateSweep.txt'
DEFAULT_ROW_FORMAT_HEADER = "{:^10}{:^10}{:^18}{:^18}"
DEFAULT_ROW_FORMAT_DATA = "{:< 10.6f}{:> 10.3f}{:< 18.7e}{:< 18.7e}"

DEFAULT_SD_KEITHLEY_GPIB = 23
DEFAULT_GATE_KEITHLEY_GPIB = 22

# for ramping output on and off
DEFAULT_V_GATE_RAMP_STEP = 100E-3
DEFAULT_V_SD_RAMP_STEP = 1E-4

DEFAULT_SD_MAX_CURRENT = 10E-6
DEFAULT_SD_DELAY = 0
DEFAULT_V_SD = 4E-3
DEFAULT_SD_NUM_POINTS = 1

DEFAULT_GATE_MAX_CURRENT = 1E-6
DEFAULT_GATE_DELAY = 0
DEFAULT_V_GATE_SWEEP_START = -1.0
DEFAULT_V_GATE_SWEEP_STOP = 1.5
DEFAULT_V_GATE_SWEEP_STEP = 0.02

from keithley import Keithley2400
import time
import numpy
import os
import matplotlib.pyplot as plt


# convenience function for updating measurement parameters
def updateIfNew(oldValue, message):
    newValue = raw_input(message + ' (' + str(oldValue) + '): ')
    print newValue
    if newValue == '':
        return oldValue
    else:
        return newValue


class gateSweep(object):
    def __init__(self):
        self.savePath = DEFAULT_SAVE_PATH
        self.saveFile = DEFAULT_SAVE_FILE

        self.gateMaxCurrent = DEFAULT_GATE_MAX_CURRENT
        self.gateDelay = DEFAULT_GATE_DELAY
        self.VgateStart = DEFAULT_V_GATE_SWEEP_START
        self.VgateStop = DEFAULT_V_GATE_SWEEP_STOP
        self.VgateStep = DEFAULT_V_GATE_SWEEP_STEP

        self.sdMaxCurrent = DEFAULT_SD_MAX_CURRENT
        self.sdDelay = DEFAULT_SD_DELAY
        self.Vsd = DEFAULT_V_SD
        self.sdNumPoints = DEFAULT_SD_NUM_POINTS

        self.sdKeithley = Keithley2400(DEFAULT_SD_KEITHLEY_GPIB)
        self.gateKeithley = Keithley2400(DEFAULT_GATE_KEITHLEY_GPIB)

        self.setup()

    # set up the gate sweep parameters
    def setup(self):
        changeParams = raw_input('Change parameters [y|n]? ')
        if changeParams == 'y':
            self.savePath = str(updateIfNew(self.savePath, 'Save path'))
            self.saveFile = str(updateIfNew(self.saveFile, 'Save filename'))

            self.gateMaxCurrent = float(updateIfNew(self.gateMaxCurrent, 'Limit for I_gate'))
            self.gateDelay = float(updateIfNew(self.gateDelay, 'Gate sweep delay'))
            self.VgateStart = float(updateIfNew(self.VgateStart, 'Gate sweep starting point'))
            self.VgateStop = float(updateIfNew(self.VgateStop, 'Gate sweep stopping point'))
            self.VgateStep = float(updateIfNew(self.VgateStep, 'Gate sweep step'))

            self.sdMaxCurrent = float(updateIfNew(self.sdMaxCurrent, 'Limit for I_sd'))
            self.sdDelay = float(updateIfNew(self.sdDelay, 'Source-drain delay'))
            self.Vsd = float(updateIfNew(self.Vsd, 'Source-drain voltage'))
            self.sdNumPoints = int(updateIfNew(self.sdNumPoints, 'Source-drain points to avg over'))

            sourceDrainGPIB = int(updateIfNew(DEFAULT_SD_KEITHLEY_GPIB, 'Source-drain Keithley GPIB address'))
            gateGPIB = int(updateIfNew(DEFAULT_GATE_KEITHLEY_GPIB, 'Gate Keithley GPIB address'))
            self.sdKeithley = Keithley2400(sourceDrainGPIB)
            self.gateKeithley = Keithley2400(gateGPIB)

            if (self.VgateStop - self.VgateStart) * self.VgateStep < 0:
                print("Gate sweep step must be positive for sweeps starting low, negative for sweeps starting high")
                self.setup()

        self._configureMeasurement()

    def _configureMeasurement(self):
        self.gateKeithley.setMeasure('current')
        self.gateKeithley.write("SOURCE:VOLT:RANGE " + str(self.VgateStop))
        self.gateKeithley.setSourceDC('voltage', 0)
        self.gateKeithley.setCompliance('current', self.gateMaxCurrent)
        self.gateKeithley.setNumPoints(1)
        self.gateKeithley.setDelay(self.gateDelay)

        self.sdKeithley.setMeasure('current')
        self.sdKeithley.write("SOURCE:VOLT:RANGE " + str(self.Vsd))
        self.sdKeithley.setSourceDC('voltage', 0)
        self.sdKeithley.setCompliance('current', self.sdMaxCurrent)
        self.sdKeithley.setNumPoints(self.sdNumPoints)  # take 10 measurements at each point, average later
        self.sdKeithley.setDelay(self.sdDelay)

    # perform a measurement with two keithleys joined over the TLINK interface (see Keithley 2400 manual)
    # can acheive faster sweep speeds than non-TLINK doSweep()
    def doTLINKSweep(self):
        self.data = [[], [], [], []]  # time, V_gate, I_sd, I_gate
        self.sdKeithley._clearData()
        self.gateKeithley._clearData()

        self.gateKeithley.rampOutputOn(self.VgateStart, DEFAULT_V_GATE_RAMP_STEP)
        self.sdKeithley.rampOutputOn(self.Vsd, DEFAULT_V_SD_RAMP_STEP)

        # set up the Keithleys to use TLINK triggering
        # has to be after rampOutputOn apparently
        self.sdKeithley.setTLINK('SOURCE', 'SENSE')
        self.gateKeithley.setTLINK('SOURCE', 'SENSE')

        # collect data while gate sweeps from VgateStart to VgateStop
        numPts = self.gateKeithley.setSourceSweep('voltage', self.VgateStart, self.VgateStop, self.VgateStep,
                                                  self.gateDelay)
        self.sdKeithley.setNumPoints(numPts)

        self.gateKeithley._startNoWait()
        self.sdKeithley._startNoWait()
        self.gateKeithley._catchSRQ()
        self.sdKeithley._catchSRQ()
        self.gateKeithley._pullData()
        self.sdKeithley._pullData()

        # collect data while gate sweeps from VgateStop back to VgateStart
        numPts = self.gateKeithley.setSourceSweep('voltage', self.VgateStop, self.VgateStart, -self.VgateStep,
                                                  self.gateDelay)
        self.sdKeithley.setNumPoints(numPts)

        self.gateKeithley._startNoWait()
        self.sdKeithley._startNoWait()
        self.gateKeithley._catchSRQ()
        self.sdKeithley._catchSRQ()
        self.gateKeithley._pullData()
        self.sdKeithley._pullData()

        # turn everything off
        self.sdKeithley.rampOutputOff(self.Vsd, DEFAULT_V_SD_RAMP_STEP)
        self.gateKeithley.rampOutputOff(self.VgateStart, DEFAULT_V_GATE_RAMP_STEP)
        self.sdKeithley._stopMeasurement()
        self.gateKeithley._stopMeasurement()

        self.data[0] = self.gateKeithley.dataTime
        self.data[1] = self.gateKeithley.dataVolt
        self.data[2] = self.sdKeithley.dataCurr
        self.data[3] = self.gateKeithley.dataCurr

        print('V_gate sweep rate (V/s): ' + str(self.calcRate()))
        self.saveData(self.savePath, self.saveFile)
        self.savePlot(self.savePath, self.saveFile)

        # set up the Keithleys to stop using TLINK triggering
        self.sdKeithley.setNoTLINK()
        self.gateKeithley.setNoTLINK()

    # perform a measurement with two keithleys joined via the computer
    # the back-and-forth with the computer makes this slower than doTLINKSweep()
    def doSweep(self):
        self.data = [[], [], [], []]  # time, V_gate, I_sd, I_gate

        self.Vgate = self.gateKeithley.rampOutputOn(self.VgateStart, DEFAULT_V_GATE_RAMP_STEP)
        self.sdKeithley.rampOutputOn(self.Vsd, DEFAULT_V_SD_RAMP_STEP)

        startTime = time.time()
        # ramp up gate voltage while taking data
        while self.Vgate < self.VgateStop:
            self.data[0].append(time.time() - startTime)

            self.sdKeithley._startMeasurement()
            self.sdKeithley._pullData()
            self.sdKeithley.write("TRACE:CLEAR")
            self.gateKeithley._startMeasurement()
            self.gateKeithley._pullData()
            self.sdKeithley.write("TRACE:CLEAR")

            self.data[1].append(self.Vgate)
            # average over (self.sdNumPoints) most recent current readings
            self.data[2].append(numpy.mean(self.sdKeithley.dataCurr[-self.sdNumPoints:]))
            self.data[3].append(numpy.mean(self.gateKeithley.dataCurr[-1:]))

            self.Vgate += self.VgateStep
            self.gateKeithley.setSourceDC('voltage', self.Vgate)
        # ramp down gate voltage while taking data
        while self.Vgate > self.VgateStart:
            self.data[0].append(time.time() - startTime)

            self.sdKeithley._startMeasurement()
            self.sdKeithley._pullData()
            self.sdKeithley.write("TRACE:CLEAR")
            self.gateKeithley._startMeasurement()
            self.gateKeithley._pullData()
            self.sdKeithley.write("TRACE:CLEAR")

            self.data[1].append(self.Vgate)
            self.data[2].append(
                numpy.mean(self.sdKeithley.dataCurr[-self.sdNumPoints:]))  # average 10 most recent current readings
            self.data[3].append(numpy.mean(self.gateKeithley.dataCurr[-1:]))

            self.Vgate -= self.VgateStep
            self.gateKeithley.setSourceDC('voltage', self.Vgate)

        self.sdKeithley.rampOutputOff(self.Vsd, DEFAULT_V_SD_RAMP_STEP)
        self.gateKeithley.rampOutputOff(self.Vgate, DEFAULT_V_GATE_RAMP_STEP)

        # self.sdKeithley.saveData(DEFAULT_SAVE_PATH, DEFAULT_SAVE_FILE, 'i')
        print('V_gate sweep rate (V/s): ' + str(self.calcRate()))
        self.saveData(self.savePath, self.saveFile)
        self.savePlot(self.savePath, self.saveFile)

    def calcRate(self):
        dataLen = len(self.data[0])
        return numpy.polyfit(self.data[0][0:dataLen / 2], self.data[1][0:dataLen / 2], 1)[0]

    # save the collected Data
    # filePath must have trailing slash, fileName must have .txt extension
    # mode 'a' appends to existing file, mode 'i' increments file counter ie test0001.txt, test0002,txt

    def saveData(self, filePath=DEFAULT_SAVE_PATH, fileName=DEFAULT_SAVE_FILE, mode='i'):
        if mode == 'a':
            saveFile = open(filePath + fileName, "a+")
        elif mode == "i":
            self.saveCounter = 0
            while True:
                self.saveCounter += 1
                print "checking file: " + filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".txt"
                if not os.path.exists(filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".txt"):
                    break
            print ""
            saveFile = open(filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".txt", "a+")
        else:
            print "invalid mode"
            return -1

        saveFile.write("\n")
        # single line format
        # saveFile.write(DEFAULT_ROW_FORMAT_HEADER.format("V (volts)","I (amps)","I/V (ohms)","t (s)","?"))

        # format for importing to Origin
        saveFile.write(DEFAULT_ROW_FORMAT_HEADER.format("t", "V_gate", "I_sd", "I_gate"))
        saveFile.write("\n")
        saveFile.write(DEFAULT_ROW_FORMAT_HEADER.format("seconds", "volts", "amps", "amps"))
        saveFile.write("\n")
        for i in range(0, len(self.data[0])):
            saveFile.write(
                DEFAULT_ROW_FORMAT_DATA.format(self.data[0][i], self.data[1][i], self.data[2][i], self.data[3][i]))
            saveFile.write("\n")
        saveFile.close()

    def savePlot(self, filePath=DEFAULT_SAVE_PATH, fileName=DEFAULT_SAVE_FILE, mode='i'):
        if mode == 'a':
            saveFileName = filePath + fileName[:-4] + '.png'
        elif mode == "i":
            self.saveCounter = 0
            while True:
                self.saveCounter += 1
                print "checking file: " + filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".png"
                if not os.path.exists(filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".png"):
                    break
            print ""
            saveFileName = filePath + fileName[:-4] + "{:04d}".format(self.saveCounter) + ".png"
        else:
            print "invalid mode"
            return -1

        plt.plot(self.data[1], self.data[2], 'bs')
        plt.plot(self.data[1], self.data[3], 'ro')
        plt.title("{:< 5.3f}".format(self.calcRate()) + " V/s")
        plt.ylabel('Current (A)')
        plt.xlabel('Gate voltage (V)')
        plt.savefig(saveFileName, bbox_inches='tight')
        plt.close()

    def plotData(self):
        plt.plot(self.data[1], self.data[2], 'bs')
        plt.plot(self.data[1], self.data[3], 'ro')
        plt.title("{:< 5.3f}".format(self.calcRate()) + " V/s")
        plt.ylabel('Current (A)')
        plt.xlabel('Gate voltage (V)')
        plt.show()
