from svinterface import checkInterface

import configparser
import subprocess as sp
import sys
import os
import shutil
import tempfile
import glob
import json
import csv
from pathlib import Path

# Return values
HANDIN_YES      = 0
HANDIN_NO       = 1

# Error codes
ERR_NOCONFIG    = 100
ERR_BADCONFIG   = 101
ERR_OP          = 200
ERR_NOEXIST     = 201
ERR_BADINTERF   = 204
ERR_NOCOMPILE   = 202
ERR_FAILTEST    = 203
ERR_HANDIN_DIR  = 210
ERR_HANDIN_PERM = 211
ERR_UNKNOWN     = 255

# Colors!
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[33m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def warning_msg(msg):
        warn = bcolors.WARNING + "WARNING: " + msg + bcolors.ENDC
        print(warn)
        return warn

    @staticmethod
    def error_msg(msg):
        err = bcolors.ERROR + "ERROR: " + msg + bcolors.ENDC
        print(err)
        return err

    @staticmethod
    def stripFormatting(s):
        contents = s

        # Remove formatting characters
        contents = contents.replace(bcolors.HEADER, "")
        contents = contents.replace(bcolors.OKBLUE, "")
        contents = contents.replace(bcolors.OKGREEN, "")
        contents = contents.replace(bcolors.WARNING, "")
        contents = contents.replace(bcolors.FAIL, "")
        contents = contents.replace(bcolors.ENDC, "")
        contents = contents.replace(bcolors.BOLD, "")
        contents = contents.replace(bcolors.UNDERLINE, "")

        return contents


# We implement errors using exceptions
class Handin240Error(Exception):
    def __init__(self, message):
        errMsg = self.getError(message)
        super(Exception, self).__init__(errMsg)
        self.errno = ERR_UNKNOWN

    def getError(self, msg):
        className = self.__class__.__name__
        return "{}{}{}: {}".format(bcolors.FAIL, className, bcolors.ENDC, msg)

class NoConfigError(Handin240Error):
    def __init__(self):
        msg = "no config found. Are you sure the HW number is correct?"
        errMsg = self.getError(msg)
        super(Handin240Error, self).__init__(errMsg)
        self.errno = ERR_NOCONFIG

class ParseConfigError(Handin240Error):
    def __init__(self, exp):
        msg = "Error parsing config file:\n"
        msg += "{}\n\nPlease contact course staff.".format(exp)
        errMsg = self.getError(msg)
        super(Handin240Error, self).__init__(errMsg)
        self.errno = ERR_BADCONFIG

class FileError(Handin240Error):
    def __init__(self, files):
        if (isinstance(files, list)):
            fileStr = ", ".join(files)
        else:
            fileStr = files
        msg = "{}: files do not exist".format(fileStr)
        errMsg = self.getError(msg)
        super(Handin240Error, self).__init__(errMsg)
        self.errno = ERR_NOEXIST

class HandinDirError(Handin240Error):
    def __init__(self):
        msg = "your handin directory was not found. Are you sure "
        msg += "you are enrolled? Please contact course staff if the "
        msg += "problem persists."
        errMsg = self.getError(msg)
        super(Handin240Error, self).__init__(errMsg)
        self.errno = ERR_HANDIN_DIR

class HandinPermError(Handin240Error):
    def __init__(self):
        msg = "access to handin directory denied. Are you "
        msg += "trying to submit past the deadline? If not, please "
        msg += "contact course staff."
        errMsg = self.getError(msg)
        super(Handin240Error, self).__init__(errMsg)
        self.errno = ERR_HANDIN_PERM


def error(message):
    """Generic error message formatter.

    Args:
        message (string): A message that describes the error.

    Returns:
        (str): Formatted error message.

    """
    return bcolors.FAIL + "ERROR: " + bcolors.ENDC + message

def warning(message):
    """Generic warning message formatter.

    Args:
        message (string): A message that describes the warning.

    Returns:
        (str): Formatted warning message.

    """
    return bcolors.WARNING + "WARNING: " + bcolors.ENDC + message

def get_env(config_file):
    conf = configparser.ConfigParser()
    conf.read(config_file)
    env = dict()
    try:
        # first parse all of the defaults
        for item in conf.defaults():
            env[item[0]] = item[1]
        # hopefully won't be clobbered by defaults
        for section in conf.sections():
            for item in conf.items(section):
                env[item[0]] = item[1]
    except Exception as e:
        print('Error parsing script config file:')
        print(e)
        # Will exit, so be careful with cleanup
        sys.exit(1)
    return env

def parseCSVField(csvPath, field='Andrew ID'):
    csvReader = csv.DictReader(csvPath)
    studentList = []
    for row in csvReader:
        studentList.append(row[field])
    return studentList

def searchCfg(hwNum, cfgDir):
    """Case-insensitive search for a target config file in cfgDir.

    Args:
        hwNum (str): HW number of config file.
        cfgDir (str): Directory to search config file in.

    Returns:
        (str): Path to the config file.

    """
    fileName = hwNum + '_cfg.json'
    fileList = os.listdir(cfgDir)
    if (fileList != None):
        for f in fileList:
            if (f.lower() == fileName.lower()):
                return '{}/{}'.format(cfgDir, f)
    raise NoConfigError()

def parseConfig(configPath):
    """Parses the config JSON file. See README for how these config files must
    be formatted/defined as.

    Raises an error if the path is invalid.

    Args:
        configPath (str): A path leading to the config JSON file. Must be a
            .json file.

    Returns:
        On success:
            (dict): A dictionary that has the parsed JSON mapped onto it. See
                the json module for details on how this is defined.

    """
    if (not os.path.exists(configPath)):
        raise NoConfigError()
    configFile = open(configPath, "r")
    try:
        return json.load(configFile)
    except Exception as e:
        raise ParseConfigError(e)
    finally:
        configFile.close()

def checkJson(jsonPath):
    jsonFile = open(jsonPath, 'r')
    try:
        json.load(jsonFile)
    except Exception as e:
        raise ParseConfigError(e)

class Operation:
    """Class that holds the necessary information for a problem's operations

    Attributes:
        number (int): Problem number
        existFiles ([str]): List of files to check for existence.
        compileFiles ([str]): List of files to compile.
        testFiles ([str]): List of TA testbenches to run against. (WIP)
        specificModules ([str]): Name of modules to compile for.
        refFilePath (str): Path to where the SV reference files are. Used for
            SV module interface checking
        hasErrors (bool): True if there is an error with the problem, False
            otherwise.
        err (str): Output of error.
        useWildcard (bool): True if the problem config uses the wildcard *.
        skipCompile (bool): True if we are to skip compilation.
        silent (bool): True if we don't want to print anything to console.

    """
    def __init__(self, refFilePath=None, skipCompile=False, silent=False):
        self.number = None
        self.existFiles = None
        self.compileFiles = None
        self.testFiles = None
        self.specificModules = None
        self.refFilePath = refFilePath
        self.hasErrors = False
        self.err = ""
        self.useWildcard = False
        self.skipCompile = skipCompile
        self.silent = silent

    def clearErrors(self):
        self.hasErrors = False
        self.err = ""

    def checkWildcard(self):
        """Checks the list of files for wildcard specifiers, then adds files
        that satisfy the wildcard(s) to the list.

        Args:
            Nothing.

        Returns:
            Nothing.

        """
        tempExistFiles = set()
        tempCompileFiles = set()

        if (self.existFiles != None):
            for f in self.existFiles:
                if ("*" in f):
                # Add all the wildcard files
                    self.useWildcard = True
                    allFiles = set(glob.glob(f))
                    tempExistFiles = tempExistFiles.union(allFiles)
                else:
                    tempExistFiles.add(f)
            # Convert to a list, alphabetical order
            self.existFiles = sorted(list(tempExistFiles))
        if (self.compileFiles != None):
            for f in self.compileFiles:
                if ("*" in f):
                    allFiles = set(glob.glob(f))
                    tempCompileFiles = tempCompileFiles.union(allFiles)
                else:
                    tempCompileFiles.add(f)
            self.compileFiles = sorted(list(tempCompileFiles))

    def parseProblem(self, p):
        """Reads the config file (as a dict) and sets the appropriate
        attributes.

        Args:
            p (dict): Dict of the config file (see readme for keys).

        Returns:
            Nothing.

        """
        if (p["number"] != None):
            self.number = p["number"]
        if (p["files"] != None):
            self.existFiles = p["files"]
        if (p["compileFiles"] != None):
            self.compileFiles = p["compileFiles"]
        if (p["testFiles"] != None):
            self.testFiles = p["testFiles"]
        if (p["specificModules"] != None):
            self.specificModules = p["specificModules"]
        self.checkWildcard()

    def getOpError(self, mainFile, errType):
        """Create a formatted error message depending on what was wrong with the
        file.

        Args:
            mainFile (str): Name of a bad file.
            errType (int): Error type to classify problem with file.

        Returns:
            (str): Formatted string to display as an error.

        """
        if (errType == ERR_NOEXIST):
            errMessage = "file does not exist"
        elif (errType == ERR_NOCOMPILE):
            errMessage = "failed to compile"
        elif (errType == ERR_FAILTEST):
            errMessage = "failed TA testbench"
        elif (errType == ERR_BADINTERF):
            errMessage = "incorrect interface"
        else:
            errMessage = "unspecified error"
        return mainFile + ": " + bcolors.FAIL + errMessage + bcolors.ENDC

    def checkExistence(self):
        """Checks if every file in a file list exists within the current
        directory. Also lists what files do not exist, if any.

        Args:

        Returns:

        """
        badFileMsg = ''
        if (self.useWildcard) and (not self.silent):
            print("Files that will be handed in:")
        if (self.existFiles != None):
            for f in self.existFiles:
                if (not os.path.exists("./" + f)):
                    self.hasErrors = True
                    error = self.getOpError(f, ERR_NOEXIST) + "\n"
                    badFileMsg += error
                    self.err += error
                elif (not self.silent):
                    if (self.useWildcard):
                        print("\t{}".format(f))
                    else:
                        print(f + ": file exists, good")
        if (not self.silent):
            if (self.useWildcard):
                print("If you do not wish to hand in these files, please " +
                        "move them away from your current directory")
            if (badFileMsg):
                print(badFileMsg.strip())

    def removeOldDir(self, fileList, oldDir):
        return ", ".join(fileList).replace("{}/".format(oldDir), "")

    def checkInterface(self):
        """Checks the module interfaces provided by files in the refFilePath
        folder, if they exist.

        Args:

        Returns:

        """
        # Skip this if we're dealing with lab files
        if (self.number < 0):
            return ''
        toPrint = ''
        if (self.existFiles != None):
            for f in self.existFiles:
                fNoExt = Path(f).with_suffix('')
                testFile = './{}'.format(f)
                refFile = '{}/{}_ref.sv'.format(self.refFilePath, fNoExt)
                # Ignore this check if the reference doesn't exist
                if (not os.path.exists(refFile)):
                    continue
                compareResult = checkInterface(refFile, testFile, self.specificModules)
                # A non-empty string implies there was an error
                if (compareResult):
                    self.hasErrors = True
                    error = self.getOpError(f, ERR_BADINTERF) + '\n'
                    toPrint += error
                    self.err += error + compareResult + '\n'
                else:
                    toPrint += f + ': interface matches reference, good'
        if (toPrint) and (not self.silent):
            print(toPrint.strip())

    def compilationErrHandler(self, fileList, oldDir, err):
        self.hasErrors = True
        files = self.removeOldDir(fileList, oldDir)
        error = self.getOpError(files, ERR_NOCOMPILE) + "\n"
        if (not self.silent):
            print(error.strip())
        self.err += error
        # Need to decode output from bytes to string properly
        errOutput = err.output.decode('utf-8')
        self.err += str(errOutput) + "\n"

    def checkCompilation(self):
        """Tries to compile files from a list using VCS (or vLogan+VCS), and
        checks to see if any compilation errors arise.

        Args:

        Returns:

        """
        # Preserve old directory to return to
        oldDir = os.getcwd()
        # Actual files are located in a different directory, so construct list:
        fileList = []
        for fileName in self.compileFiles:
            # If the file path is absolute, then just append as is
            if (os.path.isabs(fileName)):
                fileList.append(fileName)
            # Otherwise need to prepend with old directory name
            else:
                fileList.append("{}/{}".format(oldDir, fileName))
        # Use tempfile's temporary directory creation. We must delete after done
        tempDir = tempfile.mkdtemp()
        os.chdir(tempDir)

        try:
            if (self.specificModules != None):
                # Command to run vlogan with files
                vloganCmd = ["vlogan", "-q", "-sverilog", "-nc"] + fileList
                try:
                    out = sp.check_output(vloganCmd, stderr=sp.STDOUT)
                except sp.CalledProcessError as e:
                    self.compilationErrHandler(fileList, oldDir, e)
                    return
                for module in self.specificModules:
                    vcsCmd = ["vcs", "-q", "-sverilog", "-nc", module]
                    try:
                        out = sp.check_output(vcsCmd, stderr=sp.STDOUT)
                    except sp.CalledProcessError as e:
                        self.compilationErrHandler(fileList, oldDir, e)
            else:
                vcsCmd = ["vcs", "-q", "-sverilog", "-nc"] + fileList
                try:
                    out = sp.check_output(vcsCmd, stderr=sp.STDOUT)
                except sp.CalledProcessError as e:
                    self.compilationErrHandler(fileList, oldDir, e)
            if (not self.silent) and (not self.hasErrors):
                files = self.removeOldDir(fileList, oldDir)
                print(files + ": file(s) compile, good")
            return
        except (KeyboardInterrupt):
            raise
        finally:
            # Cleanup
            os.chdir(oldDir)
            shutil.rmtree(tempDir)

    # TODO: checkTATB()

    def do(self):
        """Performs an operation based on the op's attributes.

        Args:

        Returns:

        """
        if (self.existFiles != None):
            self.checkExistence()
            if (self.hasErrors):
                return self.err + "\n"
        if (self.refFilePath != None):
            self.checkInterface()
            if (self.hasErrors):
                return self.err + "\n"
        if ((not self.skipCompile) and (self.compileFiles != None)):
            self.checkCompilation()
            if (self.hasErrors):
                return self.err + "\n"
        return ""

def makeOpArray(config, refFilePath=None, skipCompile=False, silent=False):
    """Create an array of Operation objects from a config dict.

    Args:
        config (dict): Dict that represents the assignment's config
        skipCompile (bool): Optional; if True then skip compilation
        silent (bool): Optional; if True then don't print anything to console

    Returns:
        ([Operation]): Array of problem ops.

    """
    opArray = []
    # Sort problem config array by problem number
    config = sorted(config, key=lambda p: p["number"])
    for problem in config:
        op = Operation(refFilePath=refFilePath, skipCompile=skipCompile, silent=silent)
        op.parseProblem(problem)
        opArray.append(op)
    return opArray

def doOpArray(opArray):
    errStringTotal = ""
    hasErrors = False
    filesToSubmit = set()

    for op in opArray:
        op.clearErrors()
        if (op.existFiles != None):
            filesToSubmit = filesToSubmit.union(set(op.existFiles))
        if (op.compileFiles != None):
            filesToSubmit = filesToSubmit.union(set(op.compileFiles))
        errString = op.do()
        if (op.hasErrors):
            hasErrors = True
            errStringTotal += writeHeaderLine("Problem {}".format(op.number), True)
            errStringTotal += errString
    return (filesToSubmit, hasErrors, errStringTotal)

def writeHeaderLine(header, filled=False):
    """Used to write a line in the header for the errors.log file.

    Args:
        header (string): Text to write in one line of the header.

    Returns:
        (string): Formatted header line string.

    """
    headerLen = 80
    maxLen = headerLen - 2;         # -2 for beginning and ending "*"
    header = " " + header + " "
    remaining = maxLen - len(header)
    firstHalf = remaining // 2
    secondHalf = remaining - firstHalf
    if (filled):
        filler = "*"
    else:
        filler = " "
    headerLine = "*" + (filler * firstHalf) + header + (filler * secondHalf) + \
                 "*" + "\n"
    return headerLine

def getOutputHeader(studentID, hwNum):
    """Writes a formatted header that details hwNum and Andrew ID.

    Args:
        studentID (str): Andrew ID of the student.

    Returns:
        (str): Populated header.

    """
    headerLine = 80 * "*" + "\n"
    outputHeader = headerLine
    outputHeader += writeHeaderLine("18240: " + hwNum)
    outputHeader += writeHeaderLine("Error log for: " + studentID)
    outputHeader += headerLine
    return outputHeader

def createErrLog(contents, path="."):
    """Writes an errors.log file with the formatting characters removed.

    Args:
        contents (str): The stuff to write to the log file.
        path (str): Path to write errors.log (by default CWD).

    Returns:
        Nothing.

    """
    fd = open(path + "/errors.log", "w")
    toWrite = bcolors.stripFormatting(contents)
    fd.write(toWrite)
    fd.close()

def writeResults(strArr, hwNum, resultsDir):
    path = "{}/{}_results.txt".format(resultsDir, hwNum)
    if (len(strArr) < 1):
        return
    fd = open(path, "w")
    toWrite = "\n\n".join(strArr)
    toWrite = bcolors.stripFormatting(toWrite)
    fd.write(toWrite)
    fd.close()
    print("Errored students written to {}".format(path))

def checkFs(studentID, studentDir):
    """Checks AFS permissions for a student.

    Args:
        studentID (str): Andrew ID of the student.
        studentDir (str): Path to the folder to check permissions for.

    Returns:
        (bool): True if student has write permissions, False otherwise (and if
            student directory does not exist).

    """
    fsCmd = ["fs", "la", studentDir]
    perms = sp.check_output(fsCmd).decode('utf-8').split('\n')
    try:
        selfPerm = ''
        for perm in perms:
            if perm.strip().startswith(studentID):
                selfPerm = perm.strip()
                break
    except ValueError:
        error("unable to figure out student permissions for handin dir. " +
              "Please contact course staff if the problem persists.")
        return False

    # Has write permissions
    return "rlidwk" in selfPerm

