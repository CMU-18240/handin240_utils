from handin240_utils.utils import *

import subprocess as sp
import os

# Sets AFS permissions such that the student may write to the directory
# Admins have usual admin permissions, and other students may not access
def openStudentPerms(studentID, path, dryrun=False, verbose=False):
    failedOnce = False
    # Initially, clear permissions and add "default" perms
    fsCmd = ["fs", "sa", path, "-clear", "-acl"]
    # These are the default permissions, without the specific student
    defaultPerms = [
        # Permissions for staff
        "ee240:ta", "rlidwka",
        "ee240:staff", "rlidwka",
        "ee240", "rlidwka",
        # Permissions for admins
        "system:administrators", "rlidwk"
    ]
    fsCmd += defaultPerms

    retVal = None
    devnull = open(os.devnull, 'w')

    try:
        if (verbose):
            print(' '.join(fsCmd))
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
    except sp.CalledProcessError as e:
        print("Unable to set default perms for {}: {}".format(path, e))
        return retVal

    fsCmd = ["fs", "sa", path, studentID, "write"]
    try:
        if (verbose):
            print(' '.join(fsCmd))
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
        retVal = None
    except sp.CalledProcessError as e:
        failedOnce = True

    # Email auth is necessary after creds merge
    fsCmd = ["fs", "sa", path, studentID + "@andrew.cmu.edu", "write"]
    try:
        if (verbose):
            print(' '.join(fsCmd))
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
        retVal = None
    except sp.CalledProcessError as e:
        if (failedOnce):
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
    failedOnce = False
    devnull = open(os.devnull, "w")
    retVal = None

    # Now change student perms
    fsCmd = ["fs", "sa", path, studentID, "read"]
    try:
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
        return retVal
    except sp.CalledProcessError as e:
        failedOnce = True

    fsCmd = ["fs", "sa", path, studentID + "@andrew.cmu.edu", "read"]
    try:
        if (not dryrun):
            sp.check_call(fsCmd, stderr=devnull)
        retVal = None
        return retVal
    except sp.CalledProcessError as e:
        if (failedOnce):
            print("Error with trying to remove permissions for {}".format(path))
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

