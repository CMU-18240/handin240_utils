from handin240_utils.utils import *

import subprocess as sp
import os

# Sets AFS permissions such that the student may write to the directory
# Admins have usual admin permissions, and other students may not access
def openStudentPerms(studentID, path, dryrun=False, verbose=False):
    fsCmd = ["fs", "sa", path, studentID, "write"]
    fsCmd2 = ["fs", "sa", path, "system:web-srv-users", "none"]
    fsCmd3 = ["fs", "sa", path, "system:ece", "none"]
    fsCmd4 = ["fs", "sa", path, "system:authuser", "none"]

    retVal = None
    devnull = open(os.devnull, 'w')
    try:
        if (verbose):
            print(' '.join(fsCmd))
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
            sp.check_call(fsCmd2, stderr=devnull)
            sp.check_call(fsCmd3, stderr=devnull)
            sp.check_call(fsCmd4, stderr=devnull)
    except sp.CalledProcessError as e:
        retVal = studentID
    devnull.close()

    return retVal

def printBadIDs(idList):
    print('\n{}Error:{} unable to set perms for'.format(bcolors.FAIL, bcolors.ENDC))
    for id in idList:
        print('\t' + id)
    print('Please check that ID is correct, and that student is in the ECE system.')

# Creates a directory for each student inside of the basePath directory. ids
# must be an array of student IDs.
def createStudentDirs(basePath, ids, dryrun=False, verbose=False):
    badIDs = []
    for student in ids:
        path = basePath + '/' + student.lower()
        if ((not dryrun) and (not os.path.exists(path))):
            os.mkdir(basePath + '/' + student.lower())
        elif (verbose):
            print('\tHandin dir already exists for ' + student.lower() + ', skipping')
        retVal = openStudentPerms(student, path, dryrun)
        if (retVal != None):
            badIDs.append(student)
    if (len(badIDs) != 0):
        printBadIDs(badIDs)

# Sets AFS permissions such that the student may no longer write to the directory
def closeStudentPerms(studentID, path, dryrun=False):
    fsCmd = ["fs", "sa", path, studentID, "read"]

    retVal = None
    devnull = open(os.devnull, "w")
    try:
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
        return retVal
    except sp.CalledProcessError as e:
        retVal = studentID
        return retVal
    finally:
        devnull.close()

def closeStudentDirs(basePath, dirs, dryrun=False):
    badIDs = []
    for studentDir in dirs:
        path = basePath + "/" + studentDir
        retVal = closeStudentPerms(studentDir, path, dryrun)
        if (retVal != None):
            badIDs.append(studentDir)
    if (len(badIDs) != 0):
        printBadIDs(badIDs)

def checkStudent(studentDir, opArray, hwNum):
    personalOutput = getOutputHeader(studentDir, hwNum)
    hasAnyErrors = False
    oldDir = os.getcwd()
    os.chdir(studentDir)

    print("\tChecking compile for {}".format(studentDir))
    for op in opArray:
        op.clearErrors()
        errString = op.do()
        if (op.hasErrors):
            hasAnyErrors = True
            personalOutput += writeHeaderLine("Problem {}".format(op.number), True)
            personalOutput += errString
    if (hasAnyErrors):
        createErrLog(personalOutput)
    # No errors, so should remove the log file
    else:
        if (os.path.exists('./errors.log')):
            os.remove('./errors.log')

    os.chdir(oldDir)
    return (hasAnyErrors, personalOutput)

def checkStudents(cfgDir, handinDir, studentList, hwNum):
    # Parse config file and do relevant operations
    cfgPath = searchCfg(hwNum, cfgDir)
    # Take the proper (case-sensitive) hwNum
    hwNum = cfgPath[cfgPath.rindex("/")+1:cfgPath.index("_cfg.json")]
    config = parseConfig(cfgDir + "/" + hwNum + "_cfg.json")
    if (config == None):
        exit(255)
    opArray = makeOpArray(config, silent=True)
    oldCwd = os.getcwd()
    os.chdir(handinDir)

    errorStudents = []
    for student in studentList:
        hasErrors = False
        (hasErrors, errOut) = checkStudent(student, opArray, hwNum)
        if (hasErrors):
            errorStudents.append(errOut)
    os.chdir(oldCwd)
    return errorStudents

