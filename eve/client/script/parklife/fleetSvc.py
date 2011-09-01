import service
import trinity
import uthread
import form
import uix
import util
import blue
import moniker
import copy
import state
import fleetbr
import dbg
import types
import chat
import log
import uiconst
from fleetcommon import BROADCAST_ALL, BROADCAST_NONE, BROADCAST_DOWN, BROADCAST_UP
from fleetcommon import MAX_NAME_LENGTH, FLEET_NONEID, MAX_DAMAGE_SENDERS, ALL_BROADCASTS, RECONNECT_TIMEOUT
from fleetcommon import CHANNELSTATE_NONE, CHANNELSTATE_LISTENING, CHANNELSTATE_SPEAKING, CHANNELSTATE_MAYSPEAK
FLEETBROADCASTTIMEOUT = 15
UPDATEFLEETFINDERDELAY = 60
MIN_BROADCAST_TIME = 2
RECONNECT_DELAY = 10
FLEETCOMPOSITION_CACHE_TIME = 60
MAX_NUM_BROADCASTS = 500
MAX_NUM_LOOTEVENTS = 500

class ServiceStopped(Exception):
    __guid__ = 'fleet.ServiceStopped'


class FleetSvc(service.Service):
    __guid__ = 'svc.fleet'
    __notifyevents__ = ['OnFleetBroadcast',
     'ProcessSessionChange',
     'OnFleetInvite',
     'OnFleetJoin',
     'OnFleetJoinReject',
     'OnFleetLeave',
     'OnFleetMove',
     'OnFleetMemberChanged',
     'OnFleetMoveFailed',
     'OnFleetWingAdded',
     'OnFleetWingDeleted',
     'OnFleetSquadAdded',
     'OnFleetSquadDeleted',
     'OnSquadActive',
     'OnWingActive',
     'OnFleetActive',
     'OnFleetStateChange',
     'OnJumpBeaconChange',
     'OnBridgeModeChange',
     'OnFleetWingNameChanged',
     'OnFleetSquadNameChanged',
     'OnVoiceMuteStatusChange',
     'OnExcludeFromVoiceMute',
     'OnAddToVoiceMute',
     'OnFleetOptionsChanged',
     'OnJoinedFleet',
     'OnLeftFleet',
     'OnFleetJoinRequest',
     'OnFleetJoinRejected',
     'OnJoinRequestUpdate',
     'OnContactChange',
     'OnSpeakingEvent',
     'OnFleetLootEvent']
    __exportedcalls__ = {'Invite': [],
     'LeaveFleet': [],
     'IsMember': [],
     'GetMembers': [],
     'GetWings': [],
     'GetMembersInWing': [],
     'GetMembersInSquad': [],
     'ChangeWingName': [],
     'ChangeSquadName': [],
     'MoveMember': [],
     'SetBooster': [],
     'Regroup': [],
     'GetActiveBeacons': [],
     'HasActiveBeacon': [],
     'GetActiveBeaconForChar': [],
     'GetActiveBridgeForShip': [],
     'HasActiveBridge': [],
     'CanJumpThrough': [],
     'CurrentFleetBroadcastOnItem': [],
     'GetCurrentFleetBroadcastOnItem': [],
     'GetFleetLocationAndInfo': [],
     'GetFleetComposition': [],
     'DistanceToFleetMate': [],
     'SetVoiceMuteStatus': [],
     'IsVoiceMuted': [],
     'GetChannelMuteStatus': [],
     'ExcludeFromVoiceMute': [],
     'AddToVoiceMute': [],
     'IsExcludedFromMute': [],
     'GetExclusionList': [],
     'AddFavorite': [],
     'AddFavoriteSquad': [],
     'RemoveFavorite': [],
     'GetFavorites': [],
     'GetMemberInfo': [],
     'GetOptions': [],
     'SetOptions': [],
     'SetAutoJoinVoice': [],
     'IsDamageUpdates': [],
     'SetDamageUpdates': [],
     'CanIJoinChannel': [],
     'AddToVoiceChat': []}
    __startupdependencies__ = ['settings']

    def Run(self, *etc):
        service.Service.Run(self, *etc)
        self.semaphore = uthread.Semaphore()
        self.Clear()
        sm.FavourMe(self.OnFleetMemberChanged)



    def Clear(self):
        self.leader = None
        self.initedFleet = None
        self.members = {}
        self.wings = {}
        self.targetTags = {}
        self.fleetState = None
        self.activeBeacon = {}
        self.activeBridge = {}
        self.fleetID = None
        self.fleet = None
        self.isMutedByLeader = {}
        self.isExcludedFromMuting = {}
        self.favorites = []
        self.options = util.KeyVal(isFreeMove=False, isVoiceEnabled=False, isRegistered=False)
        self.isAutoJoinVoice = False
        self.isDamageUpdates = True
        self.joinRequests = {}
        self.CleanupBroadcasts()
        self.currentBroadcastOnItem = {}
        self.targetBroadcasts = {}
        self.currentTargetBroadcast = {}
        self.activeStatus = None
        self.locationUpdateRegistrations = {}
        self.lastBroadcast = util.KeyVal(name=None, timestamp=0)
        self.voiceHistory = []
        self.broadcastHistory = []
        self.broadcastScope = settings.user.ui.Get('fleetBroadcastScope', BROADCAST_ALL)
        self.updateThreadRunning = False
        self.lootHistory = []
        self.memberHistory = []
        self.fleetComposition = None
        self.fleetCompositionTimestamp = 0
        self.expectingInvite = None



    def CleanupBroadcasts(self):
        for (itemID, (gbID, gbState, data,),) in getattr(self, 'currentBroadcastOnItem', {}).iteritems():
            sm.GetService('state').SetState(itemID, gbState, False, gbID, *data)




    def Stop(self, *etc):
        service.Service.Stop(self, *etc)
        if session.fleetid and len(self.members) > 0:
            self.LogInfo('I will attempt to reconnect to this fleet', session.fleetid, ' when the client starts up again')
            settings.char.ui.Set('fleetReconnect', (session.fleetid, blue.os.GetTime()))
        self.Clear()
        self.leader = None
        self.members = None
        self.fleetTags = None
        self.fleetState = None
        self.activeBeacon = None
        self.activeBridge = None



    def OnFleetStateChange(self, fleetState):
        self.fleetState = fleetState



    def OnBridgeModeChange(self, shipID, solarsystemID, itemID, active):
        self.LogInfo('OnBridgeModeChange called:', shipID, solarsystemID, itemID, active)
        if active:
            self.activeBridge[shipID] = (solarsystemID, itemID)
        elif shipID in self.activeBridge:
            del self.activeBridge[shipID]



    def OnJumpBeaconChange(self, charID, solarsystemID, itemID, active):
        self.LogInfo('OnJumpBeaconChange:', charID, solarsystemID, itemID, active)
        if active:
            self.activeBeacon[charID] = (solarsystemID, itemID)
        elif charID in self.activeBeacon:
            del self.activeBeacon[charID]



    def GetTargetTag(self, itemID):
        if self.fleetState:
            return self.fleetState.targetTags.get(itemID, None)



    def CanJumpThrough(self, shipItem):
        if shipItem.groupID not in [const.groupTitan, const.groupBlackOps]:
            return False
        charID = shipItem.charID or shipItem.ownerID
        if not self.IsMember(charID):
            return False
        if not self.HasActiveBridge(shipItem.itemID):
            return False
        bridge = self.activeBridge[shipItem.itemID]
        return bridge[0]



    def HasActiveBridge(self, shipID):
        return shipID in self.activeBridge



    def GetActiveBeacons(self):
        return self.activeBeacon



    def HasActiveBeacon(self, charID):
        return charID in self.activeBeacon



    def GetActiveBridgeForShip(self, shipID):
        if shipID not in self.activeBridge:
            return None
        return self.activeBridge[shipID]



    def GetActiveBeaconForChar(self, charID):
        if charID not in self.activeBeacon:
            return None
        return self.activeBeacon[charID]



    def InitFleet(self):
        if self.fleet is None:
            return 
        oldOptions = self.options
        initState = self.fleet.GetInitState()
        self.fleetID = initState.fleetID
        self.members = initState.members
        self.wings = initState.wings
        self.options = initState.options
        self.isMutedByLeader = initState.isMutedByLeader
        self.isExcludedFromMuting = initState.isExcludedFromMuting
        cfg.eveowners.Prime(self.members.keys())
        self.fleetMemberLocations = {}
        if oldOptions != self.options:
            sm.ScatterEvent('OnFleetOptionsChanged_Local', oldOptions, self.options)
        sm.ScatterEvent('OnMyFleetInfoChanged')



    def SingleChoiceBox(self, title, body, choices, suppressID):
        import triui
        supp = settings.user.suppress.Get('suppress.' + suppressID, None)
        if supp is not None and not uicore.uilib.Key(uiconst.VK_SHIFT):
            return supp
        (ret, block,) = sm.GetService('gameui').RadioButtonMessageBox(text=body, title=title, buttons=uiconst.OKCANCEL, icon=triui.QUESTION, radioOptions=choices, height=210, width=300, suppText=mls.UI_SHARED_SUPPRESS5)
        if ret[0] in [uiconst.ID_CANCEL, uiconst.ID_CLOSE]:
            return 
        retNum = 1
        if ret[1] == 'radioboxOption2Selected':
            retNum = 2
        if block:
            settings.user.suppress.Set('suppress.' + suppressID, retNum)
        else:
            settings.user.suppress.Delete('suppress.' + suppressID)
        return retNum



    def CreateFleet(self):
        if session.fleetid:
            raise UserError('FleetError')
        self.fleet = sm.RemoteSvc('fleetObjectHandler').CreateFleet()
        self.LogInfo('Created fleet %s' % self.fleet)
        self.fleet.Init(self.GetMyShipTypeID())
        self.InitFleet()
        self.fleetID = self.fleet.GetFleetID()
        return True



    def Invite(self, charID, wingID, squadID, role):
        if self.fleet is None:
            if not self.CreateFleet():
                return 
        if util.IsNPC(charID) or not util.IsCharacter(charID):
            eve.Message('NotRealPilotInvite')
            return 
        msgName = None
        if charID != eve.session.charid:
            util.CSPAChargedAction('CSPAFleetCheck', self.fleet, 'Invite', charID, wingID, squadID, role)



    def WaitForLSCAndLeave(self):
        if getattr(self, 'leavingFleet', False):
            return 
        setattr(self, 'leavingFleet', True)
        loopCount = 0
        while loopCount < 20:
            if (('fleetid', session.fleetid),) in sm.GetService('LSC').channels:
                break
            self.LogInfo('Waiting for LSC channel to quit fleet')
            loopCount += 1
            blue.pyos.synchro.Sleep(500)

        setattr(self, 'leavingFleet', False)
        self.LeaveFleetNoCheck()



    def LeaveFleet(self):
        uthread.worker('Fleet::WaitForLSCAndLeave', self.WaitForLSCAndLeave)



    def LeaveFleetNoCheck(self):
        if self.fleet is None and session.fleetid:
            sm.RemoteSvc('fleetMgr').ForceLeaveFleet()
        else:
            self.fleet.LeaveFleet()
            self.Clear()



    def IsMember(self, charID):
        return charID in self.members



    def GetMembers(self):
        return self.members



    def GetWings(self):
        if self.fleet is None:
            return {}
        return self.wings



    def GetMembersInWing(self, wingID):
        members = {}
        for (mid, m,) in self.members.iteritems():
            if m.wingID == wingID:
                members[mid] = m

        return members



    def GetMembersInSquad(self, squadID):
        members = {}
        for (mid, m,) in self.members.iteritems():
            if m.squadID == squadID:
                members[mid] = m

        return members



    def ChangeWingName(self, wingID):
        if self.fleet is None:
            return 
        name = ''
        ret = uix.NamePopup(mls.UI_FLEET_CHANGEWINGNAME, mls.UI_SHARED_TYPEINNAME, name, maxLength=MAX_NAME_LENGTH)
        if ret is not None:
            self.fleet.ChangeWingName(wingID, ret['name'][:MAX_NAME_LENGTH])



    def ChangeSquadName(self, squadID):
        if self.fleet is None:
            return 
        name = ''
        ret = uix.NamePopup(mls.UI_FLEET_CHANGESQUADNAME, mls.UI_SHARED_TYPEINNAME, name, maxLength=MAX_NAME_LENGTH)
        if ret is not None:
            self.fleet.ChangeSquadName(squadID, ret['name'][:MAX_NAME_LENGTH])



    def GetOptions(self):
        return self.options



    def SetOptions(self, isFreeMove = None, isVoiceEnabled = None):
        options = copy.copy(self.options)
        if isFreeMove != None:
            options.isFreeMove = isFreeMove
        if isVoiceEnabled != None:
            if isVoiceEnabled:
                if eve.Message('FleetConfirmVoiceEnable', {}, uiconst.YESNO, suppress=uiconst.ID_YES) != uiconst.ID_YES:
                    return 
            options.isVoiceEnabled = isVoiceEnabled
        return self.fleet.SetOptions(options)



    def SetAutoJoinVoice(self):
        self.isAutoJoinVoice = True
        sm.GetService('vivox').JoinFleetChannels()



    def SetDamageUpdates(self, isit):
        self.isDamageUpdates = isit
        self.RegisterForDamageUpdates()



    def IsDamageUpdates(self):
        return self.isDamageUpdates



    def CanIJoinChannel(self, groupType, groupID):
        isUnderMe = False
        role = eve.session.fleetrole
        if role == const.fleetRoleLeader:
            isUnderMe = True
        elif role == const.fleetRoleWingCmdr:
            mySquads = self.GetWings()[eve.session.wingid].squads.keys()
            if groupType == 'wing' and groupID == eve.session.wingid:
                isUnderMe = True
            elif groupType == 'squad' and groupID in mySquads:
                isUnderMe = True
            elif groupType == 'fleet':
                isUnderMe = True
        elif groupType == 'squad' and groupID == eve.session.squadid:
            isUnderMe = True
        elif groupType == 'wing' and groupID == eve.session.wingid:
            isUnderMe = True
        elif groupType == 'fleet':
            isUnderMe = True
        return isUnderMe



    def GetJoinRequests(self):
        if not self.joinRequests:
            self.joinRequests = self.fleet.GetJoinRequests()
        return self.joinRequests



    def GetFleetHierarchy(self, members = None):
        if members is None:
            members = self.GetMembers()
        ret = {'commander': None,
         'wings': {},
         'squads': {},
         'name': ''}
        for (wingID, wing,) in self.GetWings().iteritems():
            ret['wings'][wingID] = {'commander': None,
             'squads': wing.squads.keys(),
             'name': wing.name}
            for (squadID, squad,) in wing.squads.iteritems():
                ret['squads'][squadID] = {'commander': None,
                 'members': [],
                 'name': squad.name}


        ast = self.GetActiveStatus()
        if ast is None:
            ret['active'] = False
            for (wingID, wing,) in ret['wings'].iteritems():
                wing['active'] = False

            for (squadID, squad,) in ret['squads'].iteritems():
                squad['active'] = False

        else:
            ret['active'] = ast.fleet
            for (wingID, wing,) in ret['wings'].iteritems():
                wing['active'] = ast.wings.get(wingID, False)

            for (squadID, squad,) in ret['squads'].iteritems():
                squad['active'] = ast.squads.get(squadID, False)

        for rec in members.itervalues():
            if rec.squadID:
                self.AddToFleet(ret, rec)

        return ret



    def AddToFleet(self, fleet, rec):
        if rec.squadID != -1:
            squad = fleet['squads'][rec.squadID]
            if rec.role == const.fleetRoleSquadCmdr:
                squad['commander'] = rec.charID
                squad['members'].insert(0, rec.charID)
            elif rec.role == const.fleetRoleMember:
                squad['members'].append(rec.charID)
            else:
                log.LogError('Unknown role in squad!', rec.role)
        elif rec.wingID != -1:
            wing = fleet['wings'][rec.wingID]
            if rec.role == const.fleetRoleWingCmdr:
                wing['commander'] = rec.charID
        elif rec.role == const.fleetRoleLeader:
            fleet['commander'] = rec.charID
        else:
            log.LogTraceback()
            log.LogError("don't know how to add this guy!", dbg.Prettify(rec), str(rec))



    def MoveMember(self, charID, wingID, squadID, role, roleBooster = None):
        self.CheckIsInFleet()
        if charID == session.charid:
            myself = self.members[session.charid]
            if myself.job & const.fleetJobCreator == 0:
                if role > myself.role:
                    if eve.Message('FleetConfirmDemoteSelf', {}, uiconst.YESNO) != uiconst.ID_YES:
                        return 
        if wingID is None:
            wingID = FLEET_NONEID
        if squadID is None:
            squadID = FLEET_NONEID
        if self.fleet.MoveMember(charID, wingID, squadID, role, roleBooster):
            sm.ScatterEvent('OnFleetMemberChanging', charID)



    def SetBooster(self, charID, roleBooster):
        self.CheckIsInFleet()
        if self.fleet.SetBooster(charID, roleBooster):
            sm.ScatterEvent('OnFleetMemberChanging', charID)



    def CreateWing(self):
        self.CheckIsInFleet()
        wingID = self.fleet.CreateWing()
        if wingID:
            self.CreateSquad(wingID)



    def DeleteWing(self, wingID):
        self.CheckIsInFleet()
        self.fleet.DeleteWing(wingID)



    def CreateSquad(self, wingID):
        self.CheckIsInFleet()
        self.fleet.CreateSquad(wingID)



    def DeleteSquad(self, wingID):
        self.CheckIsInFleet()
        self.fleet.DeleteSquad(wingID)



    def MakeLeader(self, charID):
        self.fleet.MakeLeader(charID)



    def KickMember(self, charID):
        if charID == eve.session.charid:
            self.LeaveFleet()
        else:
            self.fleet.KickMember(charID)



    def __VerifyRightsToRestrict(self, channel):
        return True
        ret = False
        if session.fleetrole > 3:
            ret = False
        elif session.fleetrole == 3:
            squads = self.GetFleetHierarchy()['squads']
            if squads[channel]['commander'] == session.charid:
                ret = True
        elif session.fleetrole == 2:
            wings = self.GetFleetHierarchy()['wings']
            if wings[channel]['commander'] == session.charid:
                ret = True
        elif session.fleetrole == 1:
            if session.fleetid == channel[1]:
                ret = True
        if not ret:
            raise UserError('FleetNotAllowed')



    def AddToVoiceChat(self, channelName):
        return self.fleet.AddToVoiceChat(channelName)



    def IsVoiceMuted(self, channel):
        channel = self.FixChannel(channel)
        if self.isMutedByLeader.has_key(channel) and self.isMutedByLeader[channel] == True and eve.session.charid not in self.isExcludedFromMuting[channel]:
            return True
        else:
            return False



    def GetChannelMuteStatus(self, channel):
        channel = self.FixChannel(channel)
        if self.isMutedByLeader.has_key(channel):
            return self.isMutedByLeader[channel]
        else:
            return False



    def SetVoiceMuteStatus(self, status, channel):
        channel = self.FixChannel(channel)
        if self._FleetSvc__VerifyRightsToRestrict(channel):
            self.fleet.SetVoiceMuteStatus(status, channel)



    def ExcludeFromVoiceMute(self, charid, channel = None):
        if channel is None:
            channel = self.GetMyVoiceChannel()
        channel = self.FixChannel(channel)
        if self._FleetSvc__VerifyRightsToRestrict(channel):
            self.fleet.ExcludeFromVoiceMute(charid, channel)
            if not self.isExcludedFromMuting.has_key(channel):
                self.isExcludedFromMuting[channel] = []
            self.isExcludedFromMuting[channel].append(charid)



    def AddToVoiceMute(self, charid, channel = None):
        if channel is None:
            channel = self.GetMyVoiceChannel()
        channel = self.FixChannel(channel)
        if self._FleetSvc__VerifyRightsToRestrict(channel):
            self.fleet.AddToVoiceMute(charid, channel)
            if not self.isExcludedFromMuting.has_key(channel):
                self.isExcludedFromMuting[channel] = []
            if charid in self.isExcludedFromMuting[channel]:
                self.isExcludedFromMuting[channel].remove(charid)



    def IsExcludedFromMute(self, charid, channel):
        channel = self.FixChannel(channel)
        if self.isExcludedFromMuting.has_key(channel) and charid in self.isExcludedFromMuting[channel]:
            return True
        else:
            return False



    def GetExclusionList(self):
        return self.isExcludedFromMuting



    def GetMyVoiceChannel(self):
        myChannel = None
        if session.fleetrole == const.fleetRoleLeader:
            myChannel = ('fleetid', eve.session.fleetid)
        elif session.fleetrole == const.fleetRoleWingCmdr:
            myChannel = ('wingid', eve.session.wingid)
        elif session.fleetrole == const.fleetRoleSquadCmdr:
            myChannel = ('squadid', eve.session.squadid)
        return self.FixChannel(myChannel)



    def CanIMuteOrUnmuteCharInMyChannel(self, charID):
        CAN_MUTE = 1
        CAN_UNMUTE = -1
        CAN_NOTHING = 0
        channel = self.GetMyVoiceChannel()
        if channel is None or charID is None or not self.GetChannelMuteStatus(channel):
            return CAN_NOTHING
        else:
            member = self.members[charID]
            canMuteOrUnmute = False
            canUnmute = False
            if session.fleetrole == const.fleetRoleLeader:
                canMuteOrUnmute = True
            elif session.fleetrole == const.fleetRoleWingCmdr:
                if member.wingID == eve.session.wingid:
                    canMuteOrUnmute = True
            elif session.fleetrole == const.fleetRoleSquadCmdr:
                if member.squadID == eve.session.squadid:
                    canMuteOrUnmute = True
            if not canMuteOrUnmute:
                return CAN_NOTHING
            if self.IsExcludedFromMute(charID, channel):
                return CAN_MUTE
            return CAN_UNMUTE



    def AddFavorite(self, charID):
        self.CheckIsInFleet()
        if charID == eve.session.charid:
            return 
        if len(self.favorites) >= MAX_DAMAGE_SENDERS:
            raise UserError('FleetTooManyFavorites', {'num': MAX_DAMAGE_SENDERS})
        if charID not in self.favorites:
            self.favorites.append(charID)
            self.RegisterForDamageUpdates()
            sm.ScatterEvent('OnFleetFavoriteAdded', charID)
        wnd = sm.GetService('window').GetWindow('watchlistpanel')
        if wnd is None:
            wnd = sm.GetService('window').GetWindow('watchlistpanel', decoClass=form.WatchListPanel, maximize=1, create=1, panelID='watchlistpanel', showActions=False, panelName=mls.UI_FLEET_WATCHLIST)
        wnd.OnFleetFavoriteAdded(charID)



    def AddFavoriteSquad(self, squadID):
        for (mid, m,) in self.members.iteritems():
            if m.squadID == squadID:
                self.AddFavorite(mid)




    def RemoveFavorite(self, charID):
        self.CheckIsInFleet()
        for i in range(len(self.favorites)):
            if self.favorites[i] == charID:
                del self.favorites[i]
                break

        self.RegisterForDamageUpdates()
        if sm.StartService('vivox').GetInstantVoiceParticipant() == charID:
            sm.StartService('vivox').LeaveInstantChannel()
        sm.ScatterEvent('OnFleetFavoriteRemoved', charID)
        if not self.GetFavorites():
            self.CloseWatchlistWindow()



    def CloseWatchlistWindow(self):
        wnd = sm.GetService('window').GetWindow('watchlistpanel')
        if wnd:
            wnd.SelfDestruct()



    def GetFavorites(self):
        return self.favorites



    def GetMemberInfo(self, charID):
        member = self.members.get(charID, None)
        if member is None:
            return 
        wingKeys = self.wings.keys()
        wingNo = 0
        wingKeys.sort()
        for i in range(len(wingKeys)):
            if wingKeys[i] == member.wingID:
                wingNo = i + 1
                break

        squadKeys = []
        for w in self.wings.itervalues():
            squadKeys += w.squads.keys()

        squadNo = 0
        for i in range(len(squadKeys)):
            if squadKeys[i] == member.squadID:
                squadNo = i + 1
                break

        wing = self.wings.get(member.wingID, None)
        wingName = squadName = ''
        if wing:
            wingName = wing.name
            squad = wing.squads.get(member.squadID, None)
            if squad:
                squadName = squad.name
            if squadName == '':
                squadName = '%s %s' % (mls.UI_FLEET_SQUAD, squadNo)
        if wingName == '':
            wingName = '%s %s' % (mls.UI_FLEET_WING, wingNo)
        jobName = ''
        if member.job & const.fleetJobCreator:
            jobName += '%s' % mls.UI_FLEET_ABBREV_JOBCREATOR
        boosterName = ''
        if member.roleBooster == const.fleetBoosterFleet:
            boosterName = mls.UI_FLEET_FLEET + ' ' + mls.UI_GENERIC_BOOSTER
        elif member.roleBooster == const.fleetBoosterWing:
            boosterName = mls.UI_FLEET_WING + ' ' + mls.UI_GENERIC_BOOSTER
        elif member.roleBooster == const.fleetBoosterSquad:
            boosterName = mls.UI_FLEET_SQUAD + ' ' + mls.UI_GENERIC_BOOSTER
        roleName = ''
        if member.role in (const.fleetRoleLeader, const.fleetRoleWingCmdr, const.fleetRoleSquadCmdr):
            pre = {const.fleetRoleLeader: mls.UI_FLEET_FLEET,
             const.fleetRoleWingCmdr: mls.UI_FLEET_WING,
             const.fleetRoleSquadCmdr: mls.UI_FLEET_SQUAD}[member.role]
            roleName = '%s %s' % (pre, mls.UI_FLEET_COMMANDER)
        else:
            roleName = mls.UI_FLEET_SQUADMEMBER
        ret = util.KeyVal(charID=charID, charName=cfg.eveowners.Get(charID).name, wingID=member.wingID, wingName=wingName, squadID=member.squadID, squadName=squadName, role=member.role, roleName=roleName, job=member.job, jobName=jobName, booster=member.roleBooster, boosterName=boosterName)
        return ret



    def RegisterForDamageUpdates(self):
        fav = [None, self.favorites][self.isDamageUpdates]
        sm.RemoteSvc('fleetMgr').RegisterForDamageUpdates(fav)



    def Regroup(self):
        bp = sm.StartService('michelle').GetRemotePark()
        if bp is not None:
            bp.FleetRegroup()



    def GetNearestBall(self, fromBall = None, getDist = 0):
        ballPark = sm.GetService('michelle').GetBallpark()
        if not ballPark:
            return 
        lst = []
        validNearBy = [const.groupAsteroidBelt,
         const.groupMoon,
         const.groupPlanet,
         const.groupWarpGate,
         const.groupStargate,
         const.groupStation]
        for (ballID, ball,) in ballPark.balls.iteritems():
            slimItem = ballPark.GetInvItem(ballID)
            if slimItem and slimItem.groupID in validNearBy:
                if fromBall:
                    dist = trinity.TriVector(ball.x - fromBall.x, ball.y - fromBall.y, ball.z - fromBall.z).Length()
                    lst.append((dist, ball))
                else:
                    lst.append((ball.surfaceDist, ball))

        lst.sort()
        if getDist:
            return lst[0]
        if lst:
            return lst[0][1]



    def CurrentFleetBroadcastOnItem(self, itemID, gbType = None):
        (currGBID, currGBType, currGBData,) = self.currentBroadcastOnItem.get(itemID, (None, None, None))
        if gbType in (None, currGBType):
            return currGBData
        else:
            return 



    def GetCurrentFleetBroadcastOnItem(self, itemID):
        return self.currentBroadcastOnItem.get(itemID, (None, None, None))



    def CheckIsInFleet(self, inSpace = False):
        if self.fleet is None:
            raise UserError('FleetNotInFleet')
        if inSpace and not eve.session.solarsystemid:
            raise UserError('FleetCannotDoInStation')



    def GetFleetLocationAndInfo(self):
        ret = sm.StartService('michelle').GetRemotePark().GetFleetLocationAndInfo()
        for (memberID, inf,) in ret.iteritems():
            ball = util.KeyVal(x=inf.pos[0], y=inf.pos[1], z=inf.pos[2])
            nearestBallID = self.GetNearestBall(ball).id
            inf.nearestBallID = nearestBallID
            nearestName = cfg.evelocations.Get(nearestBallID).name

        return ret



    def GetFleetComposition(self):
        if self.fleet is None:
            return 
        now = blue.os.GetTime()
        if self.fleetCompositionTimestamp < now:
            self.LogInfo('Fetching fleet composition')
            self.fleetComposition = self.fleet.GetFleetComposition()
            self.fleetCompositionTimestamp = now + FLEETCOMPOSITION_CACHE_TIME * const.SEC
        return self.fleetComposition



    def DistanceToFleetMate(self, solarSystemID, nearID):
        toSystem = cfg.evelocations.Get(solarSystemID)
        if toSystem is None or eve.session.solarsystemid2 is None:
            raise AttributeError('Invalid solarsystem')
        fromSystem = cfg.evelocations.Get(eve.session.solarsystemid2)
        dist = uix.GetLightYearDistance(fromSystem, toSystem)
        jumps = sm.StartService('pathfinder').GetJumpCountFromCurrent(solarSystemID)
        eve.Message('MapDistance', {'fromSystem': cfg.FormatConvert(LOCID, eve.session.solarsystemid2),
         'toSystem': cfg.FormatConvert(LOCID, solarSystemID),
         'dist': dist,
         'jumps': int(jumps)})



    def GetActiveStatus(self):
        if self.activeStatus is None:
            if session.solarsystemid is None or session.fleetid is None:
                return util.KeyVal(fleet=False, wings={}, squads={})
            self.activeStatus = sm.RemoteSvc('fleetMgr').GetActiveStatus()
        return self.activeStatus



    def GetVoiceChannels(self):
        channelNames = sm.GetService('vivox').GetJoinedChannels()
        channels = {'fleet': None,
         'wing': None,
         'squad': None,
         'op1': None,
         'op2': None}
        for c in channelNames:
            if type(c) is types.TupleType and c[0] in ('fleetid', 'wingid', 'squadid'):
                for k in channels.keys():
                    if c[0].startswith(k):
                        channels[k] = util.KeyVal(name=c, state=self.GetVoiceChannelState(c))

            elif type(c) is not types.TupleType or not c[0].startswith('inst'):
                n = 'op1'
                if channels[n] is not None:
                    n = 'op2'
                channels[n] = util.KeyVal(name=c, state=self.GetVoiceChannelState(c))

        return channels



    def GetVoiceChannelState(self, channelName):
        channelName = self.FixChannel(channelName)
        if not sm.GetService('vivox').IsVoiceChannel(channelName):
            return CHANNELSTATE_NONE
        if self.IsVoiceMuted(channelName):
            return CHANNELSTATE_LISTENING
        speakingChannel = sm.GetService('vivox').GetSpeakingChannel()
        if type(channelName) is types.TupleType:
            channelName = channelName[0]
        if speakingChannel == channelName:
            return CHANNELSTATE_SPEAKING
        return CHANNELSTATE_MAYSPEAK



    def RejectJoinRequest(self, charID):
        self.fleet.RejectJoinRequest(charID)



    def RemoveAndUpdateFleetFinderAdvert(self, what):
        if session.fleetid is None:
            return 
        if not self.IsBoss():
            return 
        if not getattr(self.options, 'isRegistered', False):
            return 
        ret = sm.ProxySvc('fleetProxy').RemoveFleetFinderAdvert()
        if ret:
            if eve.Message('FleetUpdateFleetFinderAd_%s' % what, {}, uiconst.YESNO, suppress=uiconst.ID_YES) == uiconst.ID_YES:
                self.OpenRegisterFleetWindow(ret)



    def BroadcastTimeRestriction(self, name):
        if self.lastBroadcast.name == name and self.lastBroadcast.timestamp + MIN_BROADCAST_TIME * SEC > blue.os.GetTime() or self.lastBroadcast.timestamp + int(float(MIN_BROADCAST_TIME) / 3.0 * float(SEC)) > blue.os.GetTime():
            self.LogInfo('Will not send broadcast', name, 'as not enough time has passed since the last one')
            return True
        else:
            self.lastBroadcast.name = name
            self.lastBroadcast.timestamp = blue.os.GetTime()
            return False



    def SendGlobalBroadcast(self, name, itemID):
        self.CheckIsInFleet(inSpace=True)
        if self.BroadcastTimeRestriction(name):
            return 
        if name not in ALL_BROADCASTS:
            raise RuntimeError('Illegal broadcast')
        self.fleet.SendBroadcast(name, self.broadcastScope, itemID)



    def SendBubbleBroadcast(self, name, itemID):
        self.CheckIsInFleet(inSpace=True)
        if self.BroadcastTimeRestriction(name):
            return 
        if name not in ALL_BROADCASTS:
            raise RuntimeError('Illegal broadcast')
        sm.RemoteSvc('fleetMgr').BroadcastToBubble(name, self.broadcastScope, itemID)



    def SendSystemBroadcast(self, name, itemID):
        self.CheckIsInFleet(inSpace=True)
        if self.BroadcastTimeRestriction(name):
            return 
        if name not in ALL_BROADCASTS:
            raise RuntimeError('Illegal broadcast')
        sm.RemoteSvc('fleetMgr').BroadcastToSystem(name, self.broadcastScope, itemID)



    def SendBroadcast_EnemySpotted(self):
        nearestBall = self.GetNearestBall()
        nearID = None
        if nearestBall is not None:
            nearID = nearestBall.id
        self.SendGlobalBroadcast('EnemySpotted', nearID)



    def SendBroadcast_NeedBackup(self):
        nearestBall = self.GetNearestBall()
        nearID = None
        if nearestBall is not None:
            nearID = nearestBall.id
        self.SendGlobalBroadcast('NeedBackup', nearID)



    def SendBroadcast_HoldPosition(self):
        nearestBall = self.GetNearestBall()
        nearID = None
        if nearestBall is not None:
            nearID = nearestBall.id
        self.SendGlobalBroadcast('HoldPosition', nearID)



    def SendBroadcast_TravelTo(self, solarSystemID):
        self.SendGlobalBroadcast('TravelTo', solarSystemID)



    def SendBroadcast_HealArmor(self):
        self.SendBubbleBroadcast('HealArmor', session.shipid)



    def SendBroadcast_HealShield(self):
        self.SendBubbleBroadcast('HealShield', session.shipid)



    def SendBroadcast_HealCapacitor(self):
        self.SendBubbleBroadcast('HealCapacitor', session.shipid)



    def SendBroadcast_Target(self, itemID):
        if sm.GetService('target').IsInTargetingRange(itemID):
            self.SendBubbleBroadcast('Target', itemID)



    def SendBroadcast_WarpTo(self, itemID):
        self.SendSystemBroadcast('WarpTo', itemID)



    def SendBroadcast_AlignTo(self, itemID):
        self.SendSystemBroadcast('AlignTo', itemID)



    def SendBroadcast_JumpTo(self, itemID):
        self.SendSystemBroadcast('JumpTo', itemID)



    def SendBroadcast_InPosition(self):
        nearestBall = self.GetNearestBall()
        nearID = None
        if nearestBall is not None:
            nearID = nearestBall.id
        self.SendGlobalBroadcast('InPosition', nearID)



    def SendBroadcast_JumpBeacon(self):
        beacon = self.GetActiveBeaconForChar(session.charid)
        if beacon is None:
            raise UserError('NoActiveBeacon')
        self.SendGlobalBroadcast('JumpBeacon', beacon[1])



    def SendBroadcast_Location(self):
        locationID = eve.session.solarsystemid2
        nearestBall = self.GetNearestBall()
        nearID = None
        if nearestBall is not None:
            nearID = nearestBall.id
        self.SendGlobalBroadcast('Location', nearID)



    def OnFleetWingNameChanged(self, wingID, name):
        self.wings = self.fleet.GetWings()
        sm.ScatterEvent('OnFleetWingNameChanged_Local', wingID, name)
        sm.ScatterEvent('OnMyFleetInfoChanged')



    def OnFleetSquadNameChanged(self, squadID, name):
        self.wings = self.fleet.GetWings()
        sm.ScatterEvent('OnFleetSquadNameChanged_Local', squadID, name)
        sm.ScatterEvent('OnMyFleetInfoChanged')



    def OnFleetInvite(self, fleetID, inviteID, msgName, msgDict):
        _FleetSvc__fleetMoniker = moniker.GetFleet(fleetID)
        if session.fleetid is not None:
            _FleetSvc__fleetMoniker.RejectInvite(True)
            return 
        if settings.user.ui.Get('autoRejectInvitations', 0) and self.expectingInvite != fleetID:
            _FleetSvc__fleetMoniker.RejectInvite(False)
            return 
        self.expectingInvite = None
        try:
            if eve.Message(msgName, msgDict, uiconst.YESNO, default=uiconst.ID_NO, modal=False) == uiconst.ID_YES:
                self.PerformSelectiveSessionChange('fleet.acceptinvite', _FleetSvc__fleetMoniker.AcceptInvite, self.GetMyShipTypeID())
                self.fleet = _FleetSvc__fleetMoniker
                self.InitFleet()
            else:
                _FleetSvc__fleetMoniker.RejectInvite()
        except UserError as e:
            eve.Message(e.msg, e.dict)



    def OnFleetJoin(self, member):
        if member.charID == eve.session.charid:
            self.InitFleet()
            sm.GetService('tactical').InvalidateFlags()
        else:
            self.members[member.charID] = member
            self.AddToMemberHistory(member.charID, mls.UI_FLEET_MEMBERHISTORY_MEMBERJOINED % {'rank': fleetbr.GetRankName(self.members[member.charID])})
            self.UpdateFleetInfo()
            sm.GetService('tactical').InvalidateFlagsExtraLimited(member.charID)
        sm.ScatterEvent('OnFleetJoin_Local', member)
        if self.isAutoJoinVoice:
            sm.GetService('vivox').JoinFleetChannels()



    def OnFleetJoinReject(self, memberID, reason):
        msg = mls.UI_FLEET_INVITEREJECTED % {'name': cfg.eveowners.Get(memberID).name}
        if reason:
            msg += mls.UI_FLEET_REASON % {'reason': reason}
        eve.Message('CustomNotify', {'notify': msg})



    def OnFleetLeave(self, charID):
        self.AddToMemberHistory(charID, mls.UI_FLEET_MEMBERHISTORY_MEMBERLEFT)
        if charID == eve.session.charid:
            self.Clear()
        if charID in self.members:
            rec = self.members.pop(charID)
            sm.GetService('tactical').InvalidateFlagsExtraLimited(charID)
        else:
            rec = util.KeyVal(charID=charID)
        if charID in self.activeBeacon:
            del self.activeBeacon[charID]
        if charID in self.activeBridge:
            del self.activeBridge[charID]
        if charID in self.favorites:
            self.RemoveFavorite(charID)
        if charID == self.leader:
            self.leader = None
        if charID != eve.session.charid:
            if len(self.members) == 1:
                self.RemoveAndUpdateFleetFinderAdvert('LastMember')
            else:
                self.UpdateFleetInfo()
        sm.ScatterEvent('OnFleetLeave_Local', rec)



    def OnFleetMemberChanged(self, charID, fleetID, oldWingID, oldSquadID, oldRole, oldJob, oldBooster, newWingID, newSquadID, newRole, newJob, newBooster, isOnlyMember):
        self.members[charID] = util.KeyVal()
        self.members[charID].charID = charID
        self.members[charID].wingID = newWingID
        self.members[charID].squadID = newSquadID
        self.members[charID].role = newRole
        self.members[charID].job = newJob
        self.members[charID].roleBooster = newBooster
        sm.ScatterEvent('OnFleetMemberChanged_Local', charID, fleetID, oldWingID, oldSquadID, oldRole, oldJob, oldBooster, newWingID, newSquadID, newRole, newJob, newBooster)
        if oldRole != newRole:
            self.AddToMemberHistory(charID, mls.UI_FLEET_BROADCAST_FLEETMEMBERCHANGED % {'role': fleetbr.GetRoleName(newRole)})
        if oldJob != newJob:
            if newJob & const.fleetJobCreator:
                self.AddToMemberHistory(charID, mls.UI_FLEET_MEMBERHISTORY_ISBOSS)
            else:
                self.AddToMemberHistory(charID, mls.UI_FLEET_MEMBERHISTORY_ISNOLONGERBOSS)
        if newRole not in (None, -1):
            self.UpdateTargetBroadcasts(charID)
        if charID == eve.session.charid:
            self.fleetCompositionTimestamp = 0
            sm.ScatterEvent('OnMyFleetInfoChanged')
            if oldRole != newRole:
                sm.GetService('vivox').LeaveChannelByType('inst')
            if oldJob & const.fleetJobCreator == 0 and newJob & const.fleetJobCreator > 0 and not isOnlyMember:
                self.RemoveAndUpdateFleetFinderAdvert('NewBoss')
        if newJob != oldJob or newRole != oldRole:
            info = self.GetMemberInfo(charID)
            if newJob != oldJob:
                r = info.jobName
            elif newRole != oldRole:
                r = info.roleName



    def OnFleetMoveFailed(self, charID, isKicked):
        if isKicked:
            eve.Message('CustomNotify', {'notify': mls.UI_FLEET_MOVEFAILED_KICKED % {'name': cfg.eveowners.Get(charID).name}})
        else:
            eve.Message('CustomNotify', {'notify': mls.UI_FLEET_MOVEFAILED % {'name': cfg.eveowners.Get(charID).name}})



    def OnFleetWingAdded(self, wingID):
        self.wings = self.fleet.GetWings()
        sm.ScatterEvent('OnFleetWingAdded_Local', wingID)



    def OnFleetWingDeleted(self, wingID):
        self.wings = self.fleet.GetWings()
        sm.ScatterEvent('OnFleetWingDeleted_Local', wingID)



    def OnFleetSquadAdded(self, wingID, squadID):
        self.wings = self.fleet.GetWings()
        sm.ScatterEvent('OnFleetSquadAdded_Local', wingID, squadID)



    def OnFleetSquadDeleted(self, squadID):
        self.wings = self.fleet.GetWings()
        sm.ScatterEvent('OnFleetSquadDeleted_Local', squadID)



    def OnSquadActive(self, squadID, isActive):
        self.LogInfo('OnSquadActive', squadID, isActive)
        self.GetActiveStatus().squads[squadID] = isActive
        sm.ScatterEvent('OnSquadActive_Local', squadID, isActive)



    def OnWingActive(self, wingID, isActive):
        self.LogInfo('OnWingActive', wingID, isActive)
        self.GetActiveStatus().wings[wingID] = isActive
        sm.ScatterEvent('OnWingActive_Local', wingID, isActive)



    def OnFleetActive(self, isActive):
        self.LogInfo('OnFleetActive', isActive)
        self.GetActiveStatus().fleet = isActive
        sm.ScatterEvent('OnFleetActive_Local', isActive)



    def OnVoiceMuteStatusChange(self, status, channel, leader, exclusionList):
        if type(channel) is not types.TupleType:
            return 
        channel = self.FixChannel(channel)
        if status == False and self.isMutedByLeader.has_key(channel):
            self.isMutedByLeader.pop(channel)
        elif status == True:
            self.isMutedByLeader[channel] = status
        sm.GetService('vivox').LeaderGagging(channel, leader, exclusionList, state=status)
        sm.ScatterEvent('OnVoiceMuteStatusChange_Local', status, channel, leader, exclusionList)



    def OnExcludeFromVoiceMute(self, charid, channel):
        channel = self.FixChannel(channel)
        if not self.isExcludedFromMuting.has_key(channel):
            self.isExcludedFromMuting[channel] = []
        if charid not in self.isExcludedFromMuting[channel]:
            self.isExcludedFromMuting[channel].append(charid)
        sm.GetService('vivox').ExclusionChange(charid, channel, 0)
        sm.ScatterEvent('OnMemberMuted_Local', charid, channel, False)



    def OnAddToVoiceMute(self, charid, channel):
        channel = self.FixChannel(channel)
        if not self.isExcludedFromMuting.has_key(channel):
            sm.GetService('vivox').ExclusionChange(charid, channel, 1)
        elif charid in self.isExcludedFromMuting[channel]:
            for i in range(len(self.isExcludedFromMuting[channel])):
                if self.isExcludedFromMuting[channel][i] == charid:
                    del self.isExcludedFromMuting[channel][i]
                    break

        sm.GetService('vivox').ExclusionChange(charid, channel, 1)
        sm.ScatterEvent('OnMemberMuted_Local', charid, channel, True)



    def FixChannel(self, name):
        if type(name) is types.TupleType:
            if type(name[0]) is not types.TupleType:
                name = (name,)
        return name



    def OnFleetOptionsChanged(self, oldOptions, options):
        self.options = options
        if self.options.isRegistered != oldOptions.isRegistered:
            sm.ScatterEvent('OnFleetFinderAdvertChanged')
            if self.options.isRegistered:
                self.AddBroadcast('FleetFinderAdvertAdded', BROADCAST_NONE, self.GetBossID(), broadcastName=mls.UI_FLEET_BROADCAST_FLEETFINDERADVERTADDED)
        if options.isFreeMove != oldOptions.isFreeMove:
            self.AddBroadcast('FleetOptionsChanged', BROADCAST_NONE, self.GetBossID(), broadcastName=[mls.UI_FLEET_FREEMOVEUNSET, mls.UI_FLEET_FREEMOVESET][options.isFreeMove])
        if options.isVoiceEnabled != oldOptions.isVoiceEnabled:
            self.AddBroadcast('FleetOptionsChanged', BROADCAST_NONE, self.GetBossID(), broadcastName=[mls.UI_FLEET_VOICEENABLEDUNSET, mls.UI_FLEET_VOICEENABLEDSET][options.isVoiceEnabled])
        sm.ScatterEvent('OnFleetOptionsChanged_Local', oldOptions, options)



    def OnJoinedFleet(self):
        self.RefreshFleetWindow()



    def OnLeftFleet(self):
        self.CloseFleetWindow()
        self.CloseWatchlistWindow()
        self.CloseFleetCompositionWindow()
        self.CloseJoinRequestWindow()
        self.CloseRegisterFleetWindow()
        self.CloseFleetBroadcastWindow()



    def OnFleetJoinRequest(self, info):
        self.joinRequests[info.charID] = info
        eve.Message('FleetMemberJoinRequest', {'name': (OWNERID, info.charID),
         'corpname': (OWNERID, info.corpID)})
        self.OpenJoinRequestWindow()



    def OnFleetJoinRejected(self, charID):
        eve.Message('FleetJoinRequestRejected', {'name': (OWNERID, charID)})



    def OnJoinRequestUpdate(self, joinRequests):
        self.joinRequests = joinRequests
        self.OpenJoinRequestWindow()



    def OnContactChange(self, contactIDs, contactType = None):
        self.RemoveAndUpdateFleetFinderAdvert('Standing')



    def OpenJoinRequestWindow(self):
        self.CloseJoinRequestWindow()
        wnd = sm.GetService('window').GetWindow('FleetJoinRequestWindow', create=1, decoClass=form.FleetJoinRequestWindow, maximize=1)



    def CloseJoinRequestWindow(self):
        wnd = sm.GetService('window').GetWindow('FleetJoinRequestWindow')
        if wnd:
            wnd.CloseX()



    def OpenFleetCompositionWindow(self):
        self.CloseFleetCompositionWindow()
        wnd = sm.GetService('window').GetWindow('FleetComposition', create=1, decoClass=form.FleetComposition, maximize=1)



    def CloseFleetCompositionWindow(self):
        wnd = sm.GetService('window').GetWindow('FleetComposition')
        if wnd:
            wnd.CloseX()



    def CloseFleetBroadcastWindow(self):
        wnd = sm.GetService('window').GetWindow('broadcastsettings')
        if wnd:
            wnd.CloseX()



    def OpenRegisterFleetWindow(self, info = None):
        if session.fleetid is None:
            raise UserError('FleetNotFound')
        if not self.IsBoss():
            raise UserError('FleetNotCreator')
        if session.userType == const.userTypeTrial:
            if info is not None:
                return 
            raise UserError('TrialAccountRestriction', {'what': mls.UI_FLEET_TRIALCANTADDADVERT})
        if info is None and self.options.isRegistered:
            info = self.GetMyFleetFinderAdvert()
        self.CloseRegisterFleetWindow()
        wnd = sm.GetService('window').GetWindow('RegisterFleetWindow', create=1, decoClass=form.RegisterFleetWindow, fleetInfo=info)



    def CloseRegisterFleetWindow(self):
        wnd = sm.GetService('window').GetWindow('RegisterFleetWindow')
        if wnd:
            wnd.CloseX()



    def RefreshFleetWindow(self):
        self.InitFleet()
        self.CloseFleetWindow()
        wnd = sm.GetService('window').GetWindow('fleetwindow', create=1, decoClass=form.FleetWindow, maximize=1, tabIdx=0)



    def CloseFleetWindow(self):
        wnd = sm.GetService('window').GetWindow('fleetwindow')
        if wnd:
            wnd.CloseX()



    def AddBroadcast(self, name, scope, charID, solarSystemID = None, itemID = None, broadcastName = None):
        time = blue.os.GetTime()
        charName = cfg.eveowners.Get(charID).name
        if broadcastName is None:
            if name in ('WarpTo', 'AlignTo', 'JumpTo', 'FleetEvent', 'JumpBeacon', 'Target', 'TravelTo'):
                broadcastName = '%s' % getattr(mls, 'UI_FLEET_BROADCAST_%s' % name.upper())
            else:
                broadcastName = '%s %s' % (charName, getattr(mls, 'UI_FLEET_BROADCAST_%s' % name.upper()))
        broadcastExtra = None
        if name in ('InPosition', 'WarpTo', 'AlignTo', 'JumpTo'):
            broadcastExtra = cfg.evelocations.Get(itemID).name
        elif name in ('TravelTo',):
            broadcastExtra = cfg.evelocations.Get(itemID).name
        elif name in ('Location',):
            broadcastExtra = cfg.evelocations.Get(solarSystemID).name
        elif name in ('Target',):
            m = sm.GetService('michelle')
            bp = m.GetBallpark()
            slimItem = bp.GetInvItem(itemID)
            if slimItem is not None:
                broadcastExtra = cfg.invtypes.Get(slimItem.typeID).name
        where = fleetbr.GetBroadcastWhere(name)
        broadcast = util.KeyVal(name=name, charID=charID, solarSystemID=solarSystemID, itemID=itemID, time=time, charName=charName, broadcastName=broadcastName, broadcastExtra=broadcastExtra, scope=scope, where=where)
        self.broadcastHistory.insert(0, broadcast)
        if len(self.broadcastHistory) > MAX_NUM_BROADCASTS:
            self.broadcastHistory.pop()
        if self.WantBroadcast(name):
            sm.ScatterEvent('OnFleetBroadcast_Local', broadcast)



    def WantBroadcast(self, name):
        if name not in fleetbr.types.keys():
            name = 'Event'
        if settings.user.ui.Get('listenBroadcast_%s' % name, True):
            return True
        return False



    def OnFleetBroadcast(self, name, scope, charID, solarSystemID, itemID):
        self.LogInfo('OnFleetBroadcast', name, scope, charID, solarSystemID, itemID, ' I now have', len(self.broadcastHistory) + 1, 'broadcasts in my history')
        self.AddBroadcast(name, scope, charID, solarSystemID, itemID)
        if name == 'Target':
            targets = self.targetBroadcasts.setdefault(charID, [])
            if itemID in targets:
                targets.remove(itemID)
                targets.insert(0, itemID)
            else:
                targets.append(itemID)
            self.UpdateTargetBroadcasts(charID)
        else:
            stateID = getattr(state, 'gb%s' % name)
            self.BroadcastState(itemID, stateID, charID)



    def BroadcastState(self, itemID, brState, *data):
        gbID = self.NewFleetBroadcastID()
        self.currentBroadcastOnItem[itemID] = (gbID, brState, data)
        sm.GetService('state').SetState(itemID, brState, True, gbID, *data)
        blue.pyos.synchro.Sleep(FLEETBROADCASTTIMEOUT * 1000)
        (savedgbid, savedgbtype, saveddata,) = self.currentBroadcastOnItem.get(itemID, (None, None, None))
        if savedgbid == gbID:
            sm.GetService('state').SetState(itemID, brState, False, gbID, *data)
            del self.currentBroadcastOnItem[itemID]



    def CycleBroadcastScope(self):
        if self.broadcastScope == BROADCAST_DOWN:
            self.broadcastScope = BROADCAST_UP
        elif self.broadcastScope == BROADCAST_UP:
            self.broadcastScope = BROADCAST_ALL
        else:
            self.broadcastScope = BROADCAST_DOWN
        settings.user.ui.Set('fleetBroadcastScope', self.broadcastScope)
        eve.Message('FleetBroadcastScopeChange', {'name': fleetbr.GetBroadcastScopeName(self.broadcastScope)})
        sm.ScatterEvent('OnBroadcastScopeChange')



    def OnSpeakingEvent(self, charID, channelID, isSpeaking):
        if not isSpeaking:
            return 
        time = blue.os.GetTime()
        charName = cfg.eveowners.Get(charID).name
        channelName = chat.GetDisplayName(channelID)
        if type(channelID) is types.TupleType:
            if channelID[0].startswith('inst'):
                channelName = mls.UI_FLEET_INSTANT
        data = util.KeyVal(channelID=channelID, charID=charID, time=time, charName=charName, channelName=channelName)
        self.voiceHistory = [ each for each in self.voiceHistory if not (each.charID == charID and each.channelID == channelID) ]
        self.voiceHistory.insert(0, data)
        sm.ScatterEvent('OnSpeakingEvent_Local', data)



    def GetVoiceHistory(self):
        return self.voiceHistory



    def OnFleetLootEvent(self, lootEvents):
        for (k, v,) in lootEvents.iteritems():
            loot = util.KeyVal(charID=k[0], solarSystemID=session.solarsystemid2, typeID=k[1], quantity=v, time=blue.os.GetTime())
            for (i, l,) in enumerate(self.lootHistory):
                if (l.typeID, l.charID, l.solarSystemID) == (loot.typeID, loot.charID, loot.solarSystemID):
                    self.lootHistory[i].quantity += loot.quantity
                    self.lootHistory[i].time = loot.time
                    break
            else:
                self.lootHistory.insert(0, loot)


        if len(self.lootHistory) > MAX_NUM_LOOTEVENTS:
            self.lootHistory.pop()
        sm.ScatterEvent('OnFleetLootEvent_Local')



    def GetLootHistory(self):
        return self.lootHistory



    def GetBroadcastHistory(self):
        history = [ h for h in self.broadcastHistory if self.WantBroadcast(h.name) ]
        return history



    def AddToMemberHistory(self, charID, event):
        self.memberHistory.insert(0, util.KeyVal(charID=charID, event=event, time=blue.os.GetTime()))
        if len(self.memberHistory) > MAX_NUM_BROADCASTS:
            self.memberHistory.pop()



    def GetMemberHistory(self):
        return self.memberHistory



    def UpdateTargetBroadcasts(self, charID):

        def BroadcastWithLabel(itemID, label):
            gbID = self.NewFleetBroadcastID()
            self.currentTargetBroadcast[itemID] = gbID
            self.BroadcastState(itemID, state.gbTarget, charID, label)
            if self.currentTargetBroadcast.get(itemID) == gbID:
                self.targetBroadcasts[charID].remove(itemID)


        initial = self.FleetLeaderInitial(self.members[charID].role)
        for (i, id_,) in enumerate(self.targetBroadcasts.get(charID, [])):
            (gbID, gbType, data,) = self.currentBroadcastOnItem.get(id_, (None, None, None))
            if gbType == state.gbTarget:
                (prevCharID, number,) = data
                if self.IsSuperior(charID, prevCharID):
                    continue
            uthread.pool('FleetSvc::UpdateTargetBroadcasts', BroadcastWithLabel, id_, '%s%i' % (initial, i + 1))




    def FleetLeaderInitial(self, role):
        return {const.fleetRoleMember: '',
         const.fleetRoleSquadCmdr: mls.UI_FLEET_SQUADINITIAL,
         const.fleetRoleWingCmdr: mls.UI_FLEET_WINGINITIAL,
         const.fleetRoleLeader: mls.UI_FLEET_FLEETINITIAL}[role]


    FleetLeaderInitial = util.Memoized(FleetLeaderInitial)

    def GetRankOrder(self):
        return [const.fleetRoleMember,
         const.fleetRoleSquadCmdr,
         const.fleetRoleWingCmdr,
         const.fleetRoleLeader]


    GetRankOrder = util.Memoized(GetRankOrder)

    def IsSuperior(self, charID, otherCharID):

        def Rank(charID):
            return self.GetRankOrder().index(self.members[charID].role)


        return Rank(charID) > Rank(otherCharID)



    def NewFleetBroadcastID(self):
        if not hasattr(self, 'lastFleetBroadcastID'):
            self.lastFleetBroadcastID = 0
        self.lastFleetBroadcastID += 1
        return self.lastFleetBroadcastID



    def ProcessSessionChange(self, isRemote, session, change):
        if 'fleetid' in change:
            self.activeStatus = None
            self.activeBeacon = {}
            self.activeBridge = {}
            self.initedFleet = None
            myrec = self.members.get(session.charid, util.KeyVal(charID=session.charid))
            self.members = {}
            self.leader = None
            if change['fleetid'][1] is None:
                self.fleet = None
                sm.GetService('vivox').LeaveChannelByType('fleetid')
                sm.GetService('vivox').LeaveChannelByType('wingid')
                sm.GetService('vivox').LeaveChannelByType('squadid')
                sm.GetService('vivox').LeaveChannelByType('inst')
                self.favorites = []
                sm.ScatterEvent('OnFleetLeave_Local', myrec)
                sm.ScatterEvent('OnLeftFleet')
            else:
                sm.ScatterEvent('OnJoinedFleet')
            sm.GetService('tactical').InvalidateFlags()
        if 'solarsystemid' in change:
            self.CleanupBroadcasts()
            self.activeStatus = None
            status = self.GetActiveStatus()
            if session.solarsystemid is not None and session.fleetid is not None:
                status = self.RegisterForDamageUpdates()
            if status:
                self.OnFleetActive(status.fleet)
                for (wid, w,) in status.wings.iteritems():
                    self.OnWingActive(wid, w)

                for (sid, s,) in status.squads.iteritems():
                    self.OnSquadActive(sid, s)

            self.UpdateFleetInfo()
        if 'shipid' in change:
            self.UpdateFleetInfo()
        if 'charid' in change:
            if change['charid'][1] is not None:
                uthread.new(self.AttemptReconnectLazy)
        if 'corpid' in change:
            uthread.new(self.RemoveAndUpdateFleetFinderAdvert, 'ChangedCorp')



    def AttemptReconnectLazy(self):
        blue.pyos.synchro.Sleep(RECONNECT_DELAY * 1000)
        try:
            try:
                if session.fleetid is not None or session.charid is None:
                    return 
                fleetReconnect = settings.char.ui.Get('fleetReconnect', None)
                if fleetReconnect and fleetReconnect[1] > blue.os.GetTime() - RECONNECT_TIMEOUT * const.MIN:
                    self.LogInfo('I will try to reconnect to a lost fleet', fleetReconnect[0])
                    fleet = moniker.GetFleet(fleetReconnect[0])
                    fleet.Reconnect()
            except Exception as e:
                self.LogWarn('Unable to reconnect. Error =', e)

        finally:
            settings.char.ui.Set('fleetReconnect', None)




    def UpdateFleetInfo(self):
        if session.fleetid is not None and not self.updateThreadRunning:
            uthread.worker('Fleet::UpdateFleetInfoThread', self.UpdateFleetInfoThread)



    def UpdateFleetInfoThread(self):
        try:
            self.LogInfo('Starting UpdateFleetInfoThread...')
            self.updateThreadRunning = True
            blue.pyos.synchro.Sleep(UPDATEFLEETFINDERDELAY * 1000)
            if session.fleetid is None:
                return 
            if self.IsBoss() and self.options.isRegistered:
                numMembers = len(self.members)
                self.LogInfo('Calling UpdateAdvertInfo', session.solarsystemid2, numMembers)
                sm.ProxySvc('fleetProxy').UpdateAdvertInfo(numMembers)
            self.LogInfo('Calling UpdateMemberInfo')
            self.fleet.UpdateMemberInfo(self.GetMyShipTypeID())

        finally:
            self.updateThreadRunning = False




    def OnFleetMove(self):
        oldSquadID = eve.session.squadid
        oldWingID = eve.session.wingid
        self.PerformSelectiveSessionChange('fleet.finishmove', self.fleet.FinishMove)
        if sm.StartService('vivox').Enabled():
            if self.isAutoJoinVoice:
                sm.StartService('vivox').JoinFleetChannels()
            else:
                if oldSquadID != eve.session.squadid:
                    sm.StartService('vivox').LeaveChannelByType('squadid')
                if oldWingID != eve.session.wingid:
                    sm.StartService('vivox').LeaveChannelByType('wingid')



    def PerformSelectiveSessionChange(self, reason, func, *args, **keywords):
        violateSafetyTimer = 0
        if session.nextSessionChange is not None and session.nextSessionChange > blue.os.GetTime():
            if session.sessionChangeReason.startswith('fleet.'):
                violateSafetyTimer = 1
        if violateSafetyTimer > 0:
            print 'I will perform a session change even though I should wait %d more seconds' % ((session.nextSessionChange - blue.os.GetTime()) / SEC)
        kw2 = copy.copy(keywords)
        kw2['violateSafetyTimer'] = violateSafetyTimer
        kw2['wait'] = 1
        sm.StartService('sessionMgr').PerformSessionChange(reason, func, *args, **kw2)



    def IsBoss(self):
        myrec = self.GetMembers().get(eve.session.charid)
        return bool(myrec and myrec.job & const.fleetJobCreator)



    def IsCommanderOrBoss(self):
        if self.IsBoss() or session.fleetrole in (const.fleetRoleLeader, const.fleetRoleWingCmdr, const.fleetRoleSquadCmdr):
            return True
        return False



    def GetBossID(self):
        myrec = self.GetMembers()
        for (mid, m,) in self.members.iteritems():
            if m.job & const.fleetJobCreator:
                return mid




    def IsMySubordinate(self, charID):
        member = self.members.get(charID, None)
        if member is None:
            return False
        isSubordinate = False
        if session.fleetrole == const.fleetRoleLeader or session.fleetrole == const.fleetRoleWingCmdr and member.wingID == session.wingid or session.fleetrole == const.fleetRoleSquadCmdr and member.squadID == session.squadid:
            isSubordinate = True
        return isSubordinate



    def RegisterFleet(self, info):
        self.LogInfo('RegisterFleet', info)
        if session.fleetid is None:
            raise UserError('FleetNotFound')
        if not self.IsBoss():
            raise UserError('FleetNotCreator')
        isEdit = self.options.isRegistered
        sm.ProxySvc('fleetProxy').AddFleetFinderAdvert(info)
        if isEdit:
            sm.ScatterEvent('OnFleetFinderAdvertChanged')



    def UnregisterFleet(self):
        if session.fleetid is None:
            raise UserError('FleetNotFound')
        if not self.IsBoss():
            raise UserError('FleetNotCreator')
        if eve.Message('FleetRemoveFleetFinderAd', {}, uiconst.YESNO, suppress=uiconst.ID_YES) == uiconst.ID_YES:
            sm.ProxySvc('fleetProxy').RemoveFleetFinderAdvert()



    def GetFleetsForChar(self):
        return sm.ProxySvc('fleetProxy').GetAvailableFleets()



    def ApplyToJoinFleet(self, fleetID):
        self.expectingInvite = fleetID
        ret = sm.ProxySvc('fleetProxy').ApplyToJoinFleet(fleetID)
        if ret:
            raise UserError('FleetApplicationReceived')



    def AskJoinFleetFromLink(self, fleetID):
        if session.fleetid is not None:
            raise UserError('FleetYouAreAlreadyInFleet')
        fleets = self.GetFleetsForChar()
        if fleetID not in fleets:
            raise UserError('FleetJoinFleetFromLinkError')
        self.ApplyToJoinFleet(fleetID)



    def GetMyFleetFinderAdvert(self):
        if session.fleetid is None or not self.options.isRegistered:
            return 
        fleet = sm.ProxySvc('fleetProxy').GetMyFleetFinderAdvert()
        if fleet is None:
            return 
        fleet.standing = None
        if fleet.Get('solarSystemID', 0):
            numJumps = int(sm.GetService('pathfinder').GetJumpCountFromCurrent(fleet.solarSystemID))
            fleet.numJumps = numJumps
            constellationID = sm.GetService('map').GetParent(fleet.solarSystemID)
            fleet.regionID = sm.GetService('map').GetParent(constellationID)
            fleet.standing = sm.GetService('standing').GetStanding(session.charid, fleet.leader.charID)
        return fleet



    def SetListenBroadcast(self, name, isit):
        if name not in fleetbr.types.keys():
            name = 'Event'
        settings.user.ui.Set('listenBroadcast_%s' % name, isit)
        sm.ScatterEvent('OnFleetBroadcastFilterChange')



    def GetMyShipTypeID(self):
        shipTypeID = None
        if session.shipid and session.solarsystemid:
            shipTypeID = sm.GetService('godma').GetItem(session.shipid).typeID
        return shipTypeID




