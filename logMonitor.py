#!/usr/bin/python
import sys, os, re 
import time, signal, smtplib

# Globals
# Some of these can be set in the config file which will override these
config             = "/etc/logMonitor.cfg"
monitorLogFile     = "/var/log/logMonitor.log"  
logList            = []
pollSeconds        = 30                        
alertEmail         = ""
fromEmail          = "logMonitor@localhost"
smtpServer         = "localhost"
host               = ""




class logMonitor:
     # Initialize class object and register vars
     def __init__(self, logName, logFileName, reportTimeout, regExList):
        self.logFileName         = logFileName
        self.logName             = logName
        self.regEx               = []        
        self.lastReport          = 0
        self.reportTimeout       = reportTimeout
        
        # Open the logfile and find current EOF so we can begin there
        try:
            fp = open(logFileName, "r")
            fp.seek(0, 2)
            self.logSeek = fp.tell()
        except:
            logit( "Couldn't open logfile" )
        fp.close()
        # Compile each regex search term and store in "regEx" list
        for each in  regExList:
           self.regEx.append(re.compile(each))




     def checkLog(self):
        global alertEmail
        global fromEmail
        global host
        global smtpServer
        foundError = False
        errorLogs = ""


        # Open the logfile
        try:
            self.logFile = open(self.logFileName, "r")
        except:
            logit( "Cannot open logfile: " + self.logFileName )

        # Seek last location in logfile or start at beginning
        if self.logSeek != 0:
            self.logFile.seek(0, 2) 
            if self.logFile.tell() == self.logSeek:
                return
            elif self.logFile.tell() > self.logSeek:
                self.logFile.seek(self.logSeek)
            else:
                logit( "Log rotated, resetting..." )
                self.logFile.seek(0) 


        for line in self.logFile.xreadlines():
            for each in self.regEx:
               if each.search(line) != None:
                   foundError = True
                   logit( self.logName + " -- " + line[:-1] )
                   errorLogs = errorLogs + line
        self.logSeek = self.logFile.tell()
        self.logFile.close()
        if foundError == True and self.lastReport < int(time.time()):
           self.lastReport = int(time.time()) + self.reportTimeout
           message = host + ": " + self.logName + "\r\n\r\n" + errorLogs
           sendMessage(alertEmail, fromEmail, "logMonitor Warning on " + host, message, smtpServer) 



def getConfig(config):
    global pollSeconds
    global alertEmail
    global monitorLogFile
    global fromEmail
    global host
    global smtpServer
    
    reportTimeout = 3600
    foundConfig = False
    x = 0
    regExList = []
 


    host = os.popen('hostname -s').readlines()[0][:-1]
    try:
       cfg = open(config, "r")
    except:
       print "Failed to open config file: " + config 
       sys.exit(1)
    # Look for begining of specific log configuration
    #newConfig       = re.compile('^\[.*\]$')
    newConfig       = re.compile(r'\[(?!END)(.*?)\]')
    regex           = re.compile('^regex=')
    email           = re.compile('^email=')
    logfile         = re.compile('^logfile=')
    pollseconds     = re.compile('^pollseconds=')
    smtpserver      = re.compile('^smtp=')
    fromemail       = re.compile('^fromemail=')
    reporttimeout   = re.compile('^reporttimeout=')
    end             = re.compile('\[END\]')

    for each in cfg.xreadlines():
          # New configuration found.
          if newConfig.search(each) and foundConfig == False:
              logName = each[1:-2]
              foundConfig = True
              continue
          if regex.search(each) and foundConfig == True:
              regExList.append(each[6:-1])
              continue
          # Found the actual logfile config
          if logfile.search(each) and foundConfig == True:
              log = each[8:-1]
              try:
                 if os.stat(log):
                    pass
              except:
                 logit( "Failed to load logfile: " + each[8:-1] + " ...skipping" )
                 logName = ""
                 regExList = []
                 log = ""
                 foundConfig = False
              continue 
          # Found reportTimeout
          if reporttimeout.search(each) and foundConfig == True:
             try:
                reportTimeout = int(each[15:])
             except:
                logit( "reportTimeout from config file could not be converted to an integer. Defaulting to 3600" )
                reportTimeout = 3600
             continue
          # Found the end of a specific log monitorin configuration, add to log list
          if end.search(each) != None and foundConfig == True:
             if log != "" and logName != "" and len(regExList) > 0:
                logList.append(logMonitor(logName, log, reportTimeout, regExList))
                
                # Remove after testing
                logit( "Adding log file configuration: " + logName )
                for x in regExList:
                    logit( " - RegEx - " + x )
                # Remove to this point
                logName = ""
                regExList = []
                log = ""
                foundConfig = False 
             else:
                logit( "Failed to load log: " + logName + " ...skipping" )
                logName = ""
                regExList = []
                log = ""
                foundConfig = False 
             continue
          # Found email in config? Update global alertEmail
          if email.search(each):
             alertEmail = each[6:-1]
             continue
          # Found pollseconds? Update global config           
          if pollseconds.search(each):
             try:
                 pollSeconds = int(each[12:])
             except:
                 pass
             continue
          # Found the smtp server set it's value         
          if smtpserver.search(each):
             smtpServer = each[5:-1]
             continue
          # Found the from email address
          if fromemail.search(each):
             fromEmail = each[10:-1]
             continue 
          #print "Found: " + each

    cfg.close()


#############################################################
# Log logMonitor information ( Setup syslog functionailty? )
#############################################################
def logit(data):
   global monitorLogFile
   curTime = time.strftime("%Y-%m-%d %H:%M:%S")
   try:
      mLogFile = open(monitorLogFile, "a")
   except:
      return
      # Fire email warning about cannot log to disk
   try:
      mLogFile.write(curTime + " -- " + data + "\n")
   except:
      return
      # Email warning about can't write to logfile
   mLogFile.close()


#############################################################
# Email alert messages
#############################################################

def sendMessage(mailto, mailfrom, subject, message, smtpserver):
   try:
      server = smtplib.SMTP(smtpserver)
   except:
      logit ( "Error: Failed to connect to SMTP server: (" + smtpserver + ")" )
   # Prepare the message
   mesg = """To: %s\r\nFrom: %s\r\nSubject: %s\r\n\r\n%s""" % (mailto, mailfrom, subject,  message)
   # Send the message
   try:
      server.sendmail(mailfrom, mailto, mesg)
   except:
      logit ( "Error: Failed to send email message" )



###########################################
# Catch shutdown signals
##########################################
def signal_handler(signal, frame):
    logit( "Shutting down..." )
    sys.exit(0) 

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGILL, signal_handler)




if __name__ == "__main__":


    logit ( "Starting up..." )
    getConfig(config)
    while(1):
        for Logs in logList:
            Logs.checkLog()
        time.sleep(pollSeconds) 
