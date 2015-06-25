import BigWorld
import AccountCommands
import ResMgr

import base64
import cPickle
import httplib
import json
import os
import traceback
import zlib

from account_helpers import BattleResultsCache
from battle_results_shared import *
from debug_utils import *
from threading import Thread
from urlparse import urlparse
from gui.shared.utils.requesters import StatsRequester
from messenger.proto.bw import ServiceChannelManager
from functools import partial
from gui import ClientHangarSpace
from PlayerEvents import g_playerEvents

BATTLE_RESULTS_VERSION = 1
logging = True
CACHE_DIR = os.path.join(os.path.dirname(unicode(BigWorld.wg_getPreferencesFilePath(), 'utf-8', errors='ignore')), 'battle_results')
todolist = []

def fetchresult(arenaUniqueID):
    if logging:
        LOG_NOTE('fetchresult:', arenaUniqueID)
    if arenaUniqueID:
        battleResults = load(BigWorld.player().name, arenaUniqueID)
        if battleResults is not None and logging:
            LOG_NOTE('Record found')
			
        proxy = partial(__onGetResponse, None)
        BigWorld.player()._doCmdInt3(AccountCommands.CMD_REQ_BATTLE_RESULTS, arenaUniqueID, 0, 0, proxy)
    else:
        return


def __onGetResponse(callback, requestID, resultID, errorStr, ext = {}):
    if logging:
        LOG_NOTE('onGetResponse', requestID, resultID)
    if resultID != AccountCommands.RES_STREAM:
        if callback is not None:
            try:
                callback(resultID, None)
            except:
                LOG_CURRENT_EXCEPTION()

        return
    else:
        BigWorld.player()._subscribeForStream(requestID, partial(__onStreamComplete, callback))
        return


def __onStreamComplete(callback, isSuccess, data):
    if logging:
        LOG_NOTE ('Stream received:', isSuccess)
    try:
        battleResults = cPickle.loads(zlib.decompress(data))
        if logging:
            LOG_NOTE ('Stream complete:', isSuccess)
        save(BigWorld.player().name, battleResults)
    except:
        LOG_CURRENT_EXCEPTION()
        if callback is not None:
            callback(AccountCommands.RES_FAILURE, None)
	return

def getFolderNameArena(accountName, arenaUniqueID):
    battleStartTime = arenaUniqueID & 4294967295L
    battleStartDay = battleStartTime / 86400
    return os.path.join(CACHE_DIR, base64.b32encode('%s;%s' % (accountName, battleStartDay)))

def getFolderName(accountName):
    import time
    battleStartDay = int(time.time()) / 86400
    return os.path.join(CACHE_DIR, base64.b32encode('%s;%s' % (accountName, battleStartDay)))

	
def load(accountName, arenaUniqueID):
    if logging:
        LOG_NOTE('Loading: ', arenaUniqueID)
    fileHandler = None
    try:
        fileName = os.path.join(getFolderNameArena(accountName, arenaUniqueID), '%s.dat' % arenaUniqueID)
        if not os.path.isfile(fileName):
            return
        fileHandler = open(fileName, 'rb')
        version, battleResults = cPickle.load(fileHandler)
    except:
        LOG_CURRENT_EXCEPTION()

    if fileHandler is not None:
        fileHandler.close()

	return battleResults

def save_existing(directory):
	createEnvironment()

	import string, shutil
	directory = string.replace(directory, '\\\\', '/')
	directory = string.replace(directory, '\\', '/')
	
	if not os.path.exists(directory):
		os.makedirs(directory)
	
	if os.path.exists(directory):
		if logging:
			LOG_NOTE('Start working on existing files in:', directory)
		try:
			for root, directories, files in os.walk(directory):
				for fileName in files:
					if logging:
						LOG_NOTE('Processing File ', fileName)
					
					if fileName.endswith(".dat"):
						fileNameADU = os.path.join('vBAddict', fileName)
						LOG_NOTE('Processing vBAddict File ', fileNameADU)
						if not os.path.exists(fileNameADU):
							fullFileName = os.path.join(root, fileName)
							if logging:
								LOG_NOTE("Saving ", fullFileName)
							shutil.copyfile(fullFileName, fileNameADU)
		except:
			LOG_CURRENT_EXCEPTION()
	else:
		if logging:
			LOG_NOTE('Directory not found: ', directory)
		
def save(accountName, battleResults):
    if logging:
        LOG_NOTE('Saving: ', accountName)
    fileHandler = None
    try:
        arenaUniqueID = battleResults[0]
        if logging:
            LOG_NOTE('Saving results of arenaUniqueID:', arenaUniqueID)
        folderName = getFolderNameArena(accountName, arenaUniqueID)
        if logging:
            LOG_NOTE('Savefile Folder:', folderName)
        if not os.path.isdir(folderName):
            os.makedirs(folderName)
		
        fileName = os.path.join(folderName, '%s.dat' % arenaUniqueID)
        fileHandler = open(fileName, 'wb')
        cPickle.dump((BATTLE_RESULTS_VERSION, battleResults), fileHandler, -1)
		
        save_existing(folderName)
		
    except:
        LOG_CURRENT_EXCEPTION()

    if fileHandler is not None:
        fileHandler.close()


old_msg = ServiceChannelManager._ServiceChannelManager__addServerMessage
old_setup = ClientHangarSpace._VehicleAppearance._VehicleAppearance__doFinalSetup

def new_msg(self, message):
    if logging:
        LOG_NOTE('Received Message:', message)
    if message.type == 2:
        try:
			for vehTypeCompDescr, battleResult in message.data.iteritems():
				if battleResult['arenaUniqueID']>0:
					todolist.append(battleResult['arenaUniqueID'])
        except:
            LOG_CURRENT_EXCEPTION()

    old_msg(self, message)

def new_setup(self, buildIdx, model, delModel):
    if logging:
        LOG_NOTE('New Setup')
		
	save_existing(getFolderName(BigWorld.player().name))
	
	if todolist:
		if logging:
			LOG_NOTE('Start work on my ToDoList:', todolist)
			while todolist:
				temp = todolist.pop()
				fetchresult(int(temp))

	old_setup(self, buildIdx, model, delModel)


def createEnvironment():
	import os
	try:
		if not os.path.isdir('vBAddict'):
			os.makedirs('vBAddict')
		if not os.path.exists('vBAddict'):
			return
	except Exception:
		e = None
		LOG_CURRENT_EXCEPTION()
		
			
if logging:
	LOG_NOTE('BRR loaded')
ServiceChannelManager._ServiceChannelManager__addServerMessage = new_msg
ClientHangarSpace._VehicleAppearance._VehicleAppearance__doFinalSetup = new_setup
