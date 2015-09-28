# example script/class using the Keithley2400 python class to do a simple IV curve measurement


DEFAULT_SAVE_PATH = 'C:/Data/'
DEFAULT_SAVE_FILE = 'ivSweep_.txt'

# use whatever your keithley's GBIP address is
DEFAULT_GPIB_ADDR = 23  

# set sweep parameters (in volts)
DEFAULT_MIN_BIAS = -5E-3
DEFAULT_MAX_BIAS = 5E-3
DEFAULT_STEP_BIAS = 1E-4
DEFAULT_STEP_TIME = 0.1


from keithley import Keithley2400
import matplotlib.pyplot as plt
import traceback


# convenience function for updating measurement parameters
def updateIfNew(oldValue, message):
    '''prompts the user with [message], then returns whatever
    is entered, or [oldValue] if nothing was entered'''
    newValue = raw_input(message + ' (' + str(oldValue) + '): ')
    if newValue == '':
	return oldValue
    else:
	return newValue


class ivSweep(object):
    def __init__(self):
        self.savePath = DEFAULT_SAVE_PATH
        self.saveFile = DEFAULT_SAVE_FILE

	self.minBias = DEFAULT_MIN_BIAS
	self.maxBias = DEFAULT_MAX_BIAS
	self.stepBias = DEFAULT_STEP_BIAS
	self.stepTime = DEFAULT_STEP_TIME

	self.k = Keithley2400(DEFAULT_GPIB_ADDR)

	self.setup('y')

    def setup(self, changeParams=None):
	if not changeParams:
            changeParams = raw_input('Change parameters [y|N]? ')
	if changeParams =='y':
            self.savePath = str(updateIfNew(self.savePath, 'Save path '))
            self.saveFile = str(updateIfNew(self.saveFile, 'Save filename '))
	    self.minBias = float(updateIfNew(self.minBias, 'Minimum bias '))
	    self.maxBias = float(updateIfNew(self.maxBias, 'Maximum bias '))
	    self.stepBias = float(updateIfNew(self.stepBias, 'Bias step '))
	    self.stepTime = float(updateIfNew(self.stepTime, 'Time step '))
        self._configureMeasurement()

    def _configureMeasurement(self):
	self.k.setMeasure('current')
        #self.k.setSourceSweep('voltage', self.minBias, self.maxBias, self.stepBias, self.stepTime)

    def doSweep(self):
        self.k.rampOutputOn(self.minBias, self.stepBias)
        self.k.setSourceSweep('voltage', self.minBias, self.maxBias, self.stepBias, self.stepTime)  # sweep from minV to maxV
        self.k._startMeasurement()
        self.k._pullData()
        self.k.setSourceSweep('voltage', self.maxBias, self.minBias, -self.stepBias, self.stepTime)  # sweep from maxV to minV
        self.k._startMeasurement()
        self.k._pullData()
        self.k.rampOutputOff(self.minBias, self.stepBias)
        self.k._stopMeasurement()

    def plotData(self):
        plt.plot(self.k.dataVolt, self.k.dataCurr)
	plt.xlabel('Bias (V)')
	plt.ylabel('Measured current (A)')
	plt.xlim([self.minBias, self.maxBias])
	plt.show()
	plt.close()

    def saveData(self):
        fname = self.k.saveData(self.savePath, self.saveFile)
	print('saved to ' + fname)


if __name__=="__main__":

	iv = ivSweep()
	option_dict = {
			1: ['configure sweep', iv.setup], 
			2: ['do sweep', iv.doSweep], 
			3: ['plot data', iv.plotData], 
			4: ['save data', iv.saveData], 
			5: ['quit']
			}

	while True:
		print '********************'
		for key in option_dict:
			print key, option_dict[key][0]
		print ''

		try:
		    cmd = input('Enter an option [1-5]: ')
		    option_dict[cmd][1]()
	        except IndexError:
		    break
       	        except Exception as e:
		    print e
		    print traceback.format_exc()
		    pass
