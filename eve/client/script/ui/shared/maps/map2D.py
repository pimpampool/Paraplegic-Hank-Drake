import sys
import uix
import uiutil
import mathUtil
import blue
import lg
import trinity
import base
import uthread
import util
import os
import math
from math import pi
import uicls
import uiconst
from pychartdir import setLicenseCode, DrawArea
setLicenseCode('DIST-0000-05de-f7ec-ffbeURDT-232Q-M544-C2XM-BD6E-C452')
DRAWLVLREG = 1
DRAWLVLCON = 2
DRAWLVLSOL = 3
DRAWLVLSYS = 4
FLIPMAP = -1
CACHEVERSION = 8

def LtoI(v):
    if v < 2147483648L:
        return int(v)
    return ~int(~v & 4294967295L)



class Map2D(uicls.Container):
    __guid__ = 'xtriui.Map2D'
    __nonpersistvars__ = []
    __notifyevents__ = ['OnDestinationSet']

    def init(self):
        sm.RegisterNotify(self)
        self.sr.sizefactor = None
        self.sr.sizefactorsize = None
        self.sr.marks = None
        self.Reset()
        self.overlays = uicls.Container(name='overlays', parent=self, clipChildren=1, pos=(0, 0, 0, 0))
        self.sr.areas = uicls.Container(name='areas', parent=self, clipChildren=1, pos=(0, 0, 0, 0))
        self.hilite = uicls.Sprite(parent=self.overlays, pos=(0, 0, 16, 16), color=(1.0, 1.0, 1.0, 0.4), name='hilite', state=uiconst.UI_HIDDEN, texturePath='res:/UI/Texture/Shared/circleThin16.png', align=uiconst.RELATIVE)
        self.imhere = uicls.Container(name='imhere', parent=self.overlays, state=uiconst.UI_HIDDEN, align=uiconst.TOPLEFT, width=16, height=16)
        circle = uicls.Sprite(parent=self.imhere, idx=0, pos=(0, 0, 16, 16), color=(1.0, 0.0, 0.0, 1.0), name='imhere_sprite', texturePath='res:/UI/Texture/Shared/circleThin16.png', align=uiconst.RELATIVE)
        self.destination = uicls.Sprite(parent=self.overlays, pos=(0, 0, 16, 16), color=(1.0, 1.0, 0.0, 1.0), state=uiconst.UI_HIDDEN, name='destination', texturePath='res:/UI/Texture/Shared/circleThin16.png', align=uiconst.RELATIVE)
        self.sprite = uicls.Icon(name='mapsprite', parent=self, align=uiconst.TOALL, state=uiconst.UI_DISABLED, color=(1.0, 1.0, 1.0, 0.0))
        self.bgSprite = None
        self.dragging = 0
        self.ditherIn = 1
        self.dragAllowed = 0
        self.dataLayer = None
        self.dataToggle = 0
        self.dataArgs = {}
        self.dataLoaded = None
        self.needsize = None
        self.allowAbstract = 1
        self.fillSize = 0.8
        self.mouseHoverGroups = []
        self.cordsAsPortion = {}
        self.fov = None
        self.tempAngleFov = None



    def SetInfoMode(self):
        self.updatemylocationtimer = None
        uiutil.FlushList(self.imhere.children[1:])
        for each in self.children:
            if each.name == 'frame':
                each.Close()




    def MarkAreas(self, areas = []):
        uthread.pool('Map2D::_MarkAreas', self._MarkAreas, areas)



    def _MarkAreas(self, areas):
        size = self.absoluteRight - self.absoluteLeft
        uix.Flush(self.sr.areas)
        for area in areas:
            (id, hint, (absX, absY, absZ,), radius, color,) = area
            maxdist = self.GetMaxDist()
            sizefactor = size / 2 / maxdist * self.fillSize
            x = FLIPMAP * absX * sizefactor / float(size) + 0.5
            y = absZ * sizefactor / float(size) + 0.5
            rad = radius * sizefactor / float(size)
            mark = uicls.Sprite(parent=self.sr.areas, name='area', left=int(int(x * size) - mark.width / 2), top=int(int(y * size) - mark.height / 2 + 1), width=int(rad * size * 2), height=int(rad * size * 2), state=uiconst.UI_DISABLED, texturePath='res:/UI/Texture/circle_full.png', color=(1.0, 0.2, 0.2, 1.0))
            mark.sr.x = x
            mark.sr.y = y
            mark.sr.rad = rad




    def SetMarks(self, marks = []):
        uthread.pool('Map2D::SetMarks', self._SetMarks, marks)



    def _SetMarks(self, marks):
        if not uiutil.IsUnder(self, uicore.desktop):
            return 
        for i in xrange(0, len(marks), 4):
            id = marks[i]
            hint = marks[(i + 1)]
            uiutil.Update(self, 'Map2D::_SetMarks')
            size = max(1, self.absoluteRight - self.absoluteLeft)
            (x, y,) = self.GetCordsByKeyAsPortion(id, size)
            if x is None or y is None:
                return 
            if self.sr.marks is None:
                self.sr.marks = uicls.Container(name='marks', parent=self, align=uiconst.TOALL, pos=(0, 0, 0, 0), idx=0, state=uiconst.UI_DISABLED)
            mark = uicls.Sprite(parent=self.sr.marks, name='area', left=x - mark.width / 2, top=y - mark.height / 2 + 1, width=128, height=128, state=uiconst.UI_PICKCHILDREN, texturePath='res:/UI/Texture/circle_full.png', color=(1.0, 1.0, 1.0, 0.21))
            if hint:
                uicls.Label(text=hint, parent=self.sr.marks, left=mark.left + mark.width, top=mark.top + 2, autowidth=False, width=min(128, max(64, size - mark.left - mark.width)), state=uiconst.UI_NORMAL)




    def OnDestinationSet(self, destinationID, *args):
        if self is None or self.destroyed:
            return 
        self.CheckDestination()



    def Reset(self):
        self.portion = 0.75
        self.areas = []
        self.orbs = []
        self.hilite = None
        self.imhere = None
        self.overlays = None
        self.lasthilite = None
        self.pickradius = 6
        self.mapitems = []
        self.outsideitems = []
        self.ids = None
        self.idlevel = None
        self.drawlevel = None
        self.clipped = 0
        self.updatemylocationtimer = None
        self.showingtempangle = None
        self.settings = None



    def _OnClose(self):
        sm.UnregisterNotify(self)
        self.updatemylocationtimer = None
        for each in self.overlays.children:
            if each.name == 'destinationline':
                if hasattr(each, 'renderObject') and each.renderObject and len(each.renderObject.children):
                    for _each in each.renderObject.children:
                        _each.object.numPoints = 0
                        del _each.object.vectorCurve.keys[:]
                        each.renderObject.children.remove(_each)

                each.renderObject = None
                each.Close()

        self.OnSelectItem = None
        self.Reset()



    def Draw(self, ids, idlevel, drawlevel, needsize, sprite = None):
        _settings = (ids,
         idlevel,
         drawlevel,
         needsize)
        if _settings == self.settings:
            return 
        self.settings = _settings
        lg.Info('2Dmaps', 'Drawing map, ids/idlevel/drawlevel:', ids, idlevel, drawlevel)
        if drawlevel <= idlevel:
            return 
        if drawlevel == DRAWLVLSYS and len(ids) > 1:
            ids = ids[:1]
        SIZE = needsize
        if sprite is None:
            sprite = self.sprite
        _ids = {}
        for id in ids:
            _ids[id] = ''

        ids = _ids.keys()
        endid = ''
        if len(ids) > 1:
            endid = '%s_' % ids[-1]
        self.ids = ids
        self.idlevel = idlevel
        self.drawlevel = drawlevel
        self.needsize = needsize
        imageid = '%s_%s_%s_%s_%s_%s' % (ids[0],
         '_' * max(0, len(ids) - 2),
         endid,
         idlevel,
         drawlevel,
         self.fillSize)
        imageid = imageid.replace('.', '')
        if self.drawlevel == DRAWLVLSYS:
            imageid += '_' + str(settings.user.ui.Get('solarsystemmapabstract', 0))
        lg.Info('2Dmaps', 'MapID is: %s' % imageid)
        for each in self.overlays.children:
            if each.name == 'destinationline':
                each.renderObject = None
                each.Close()

        self.cordsAsPortion = {}
        cache = self.CheckIfCached(imageid)
        if cache:
            mapitems = self.mapitems = cache['items']
            outsideitems = self.outsideitems = cache['outsideitems']
        else:
            mapitems = self.mapitems = self.GetMapData(ids, idlevel, drawlevel)
        if drawlevel == 4:
            self.DrawSolarsystem(sprite, ids, imageid, mapitems, SIZE)
            self.CheckMyLocation()
            return 
        (connections, outsideitems,) = self.GetConnectionData(ids, idlevel, drawlevel)
        self.outsideitems = outsideitems
        minx = 1e+100
        maxx = -1e+100
        minz = 1e+100
        maxz = -1e+100
        for item in mapitems:
            minx = min(minx, item.x)
            maxx = max(maxx, item.x)
            minz = min(minz, item.z)
            maxz = max(maxz, item.z)

        mw = -minx + maxx
        mh = -minz + maxz
        if not (mw and mh):
            return 
        SIZE = SIZE * 2
        drawarea = DrawArea()
        drawarea.setTransparentColor(-1)
        drawarea.setSize(SIZE, SIZE, 4278190080L)
        dotrad = [2,
         3,
         4,
         5,
         6][idlevel]
        sizefactor = min(SIZE / mw, SIZE / mh) * self.portion
        cords = {}
        for item in mapitems[:]:
            if item.groupID == const.groupRegion:
                if drawlevel != 1:
                    continue
            if item.groupID == const.groupConstellation:
                if drawlevel != 2:
                    continue
            x = int(item.x * sizefactor - int(minx * sizefactor) + (SIZE - mw * sizefactor) / 2)
            y = int(item.z * sizefactor - int(minz * sizefactor) + (SIZE - mh * sizefactor) / 2)
            cords[item.itemID] = (x,
             SIZE - y,
             dotrad,
             1,
             16777215)

        for item in self.outsideitems:
            x = int(item.x * sizefactor - int(minx * sizefactor) + (SIZE - mw * sizefactor) / 2)
            y = int(item.z * sizefactor - int(minz * sizefactor) + (SIZE - mh * sizefactor) / 2)
            cords[item.itemID] = (x,
             SIZE - y,
             dotrad,
             0,
             None)

        done = []
        i = 0
        lineWidth = 2.0
        for jumptype in connections:
            for pair in jumptype:
                (fr, to,) = pair
                if (fr, to) in done:
                    continue
                if fr in cords and to in cords:
                    drawarea.line(cords[fr][0], cords[fr][1], cords[to][0], cords[to][1], [43520, 255, 16711680][i], lineWidth)
                    drawarea.line(cords[fr][0] + 1, cords[fr][1], cords[to][0] + 1, cords[to][1], [43520, 255, 16711680][i], lineWidth)
                    drawarea.line(cords[fr][0], cords[fr][1] + 1, cords[to][0], cords[to][1] + 1, [43520, 255, 16711680][i], lineWidth)

            i += 1

        for (x, y, dotrad, cordtype, col,) in cords.itervalues():
            if cordtype == 0:
                dotrad = dotrad / 2
            drawarea.circle(x, y, dotrad, dotrad, 16777215, 16777215)

        self.areas = [ (cords[id][0],
         cords[id][1],
         cords[id][2],
         id) for id in cords.iterkeys() ]
        self.cordsAsPortion = {}
        for id in cords.iterkeys():
            self.cordsAsPortion[id] = (cords[id][0] / float(SIZE), cords[id][1] / float(SIZE))

        self.CheckMyLocation()
        self.CheckDestination()
        SIZE = SIZE / 2
        self.Cache(imageid, mapitems, outsideitems)
        self.PlaceMap(sprite, drawarea, SIZE)



    def CheckDestination(self):
        if self is None or self.destroyed:
            return 
        destination = sm.GetService('starmap').GetDestination()
        if destination and self.drawlevel == DRAWLVLSOL:
            (x, y,) = self.GetCordsByKeyAsPortion(destination)
            if x is None or y is None:
                return 
            (self.destination.sr.x, self.destination.sr.y,) = (x, y)
            self.destination.state = uiconst.UI_DISABLED
            self.RefreshOverlays(1)
        else:
            for each in self.overlays.children:
                if each.name == 'destinationline':
                    each.renderObject = None
                    each.Close()




    def GetMapData(self, ids, idlevel, drawlevel):
        mapitems = []
        mapsvc = sm.GetService('map')
        cache = mapsvc.GetMapCache()
        items = cache['items']
        hierarchy = cache['hierarchy']
        if idlevel == 0:
            for _regionID in hierarchy.iterkeys():
                if _regionID > const.mapWormholeRegionMin:
                    continue
                mapitems.append(items[_regionID].item)
                for _constellationID in hierarchy[_regionID].iterkeys():
                    if drawlevel >= 2:
                        mapitems.append(items[_constellationID].item)
                    if drawlevel == 3:
                        for _solarsystemID in hierarchy[_regionID][_constellationID].iterkeys():
                            mapitems.append(items[_solarsystemID].item)



        elif idlevel == 1:
            for regionID in ids:
                if regionID > const.mapWormholeRegionMin:
                    continue
                if util.IsRegion(regionID) and regionID in items:
                    mapitems.append(items[regionID].item)
                    for _constellationID in hierarchy[regionID].iterkeys():
                        if drawlevel >= 2:
                            mapitems.append(items[_constellationID].item)
                        if drawlevel == 3:
                            for _solarsystemID in hierarchy[regionID][_constellationID].iterkeys():
                                mapitems.append(items[_solarsystemID].item)



        elif idlevel == 2:
            for constellationID in ids:
                if constellationID > const.mapWormholeConstellationMin:
                    continue
                if util.IsConstellation(constellationID) and constellationID in items:
                    mapitems.append(items[constellationID].item)
                    _regionID = mapsvc.GetParentLocationID(constellationID)
                    for _solarsystemID in hierarchy[_regionID][constellationID].iterkeys():
                        mapitems.append(items[_solarsystemID].item)


        elif idlevel == 3:
            for solarsystemID in ids:
                if util.IsSolarSystem(solarsystemID):
                    mapitems += sm.RemoteSvc('config').GetMapObjects(solarsystemID, 0, 0, 0, 1, 0)

        return mapitems



    def GetConnectionData(self, ids, idlevel, drawlevel):
        inside = []
        outside = []
        conninfo = []
        map = sm.GetService('map')
        for id in ids:
            connections = map.GetItemConnections(int(id), drawlevel == 1, drawlevel == 2, drawlevel == 3, 0, 1)
            conninfo.extend(connections)

        reg = []
        con = []
        sol = []
        outsiders = []
        for connection in conninfo:
            (ctype, fromreg, fromcon, fromsol, stargateID, celestialID, tosol, tocon, toreg,) = connection
            (f, t,) = [(const.locationUniverse, const.locationUniverse),
             (fromreg, toreg),
             (fromcon, tocon),
             (fromsol, tosol),
             (stargateID, celestialID)][drawlevel]
            if fromreg != toreg and (f, t) not in reg:
                reg.append((f, t))
                if idlevel + 1 > DRAWLVLREG:
                    item = map.GetItem(t)
                    if item and item.itemID not in reg + con + sol and item.groupID == [None,
                     const.groupRegion,
                     const.groupConstellation,
                     const.groupSolarSystem][drawlevel]:
                        outsiders.append(item)
            elif fromcon != tocon and (f, t) not in con:
                con.append((f, t))
                if idlevel + 1 > DRAWLVLCON:
                    item = map.GetItem(t)
                    if item and item.itemID not in reg + con + sol and item.groupID == [None,
                     const.groupRegion,
                     const.groupConstellation,
                     const.groupSolarSystem][drawlevel]:
                        outsiders.append(item)
            elif fromsol != tosol and (f, t) not in sol:
                sol.append((f, t))
                if idlevel + 1 > DRAWLVLSOL:
                    item = map.GetItem(t)
                    if item and item.itemID not in reg + con + sol and item.groupID == [None,
                     const.groupRegion,
                     const.groupConstellation,
                     const.groupSolarSystem][drawlevel]:
                        outsiders.append(item)

        return ((reg, con, sol), outsiders)



    def Width(self):
        return self.absoluteRight - self.absoluteLeft



    def Height(self):
        return self.absoluteBottom - self.absoluteTop



    def MyHierarchy(self):
        return (eve.session.regionid,
         eve.session.constellationid,
         eve.session.solarsystemid2,
         eve.session.stationid)



    def PlaceMap(self, sprite, drawArea, size):
        if self is None or self.destroyed:
            return 
        surface = trinity.device.CreateOffscreenPlainSurface(size, size, trinity.TRIFMT_A8R8G8B8, trinity.TRIPOOL_SYSTEMMEM)
        surface.LoadSurfaceFromFileInMemory(drawArea.outPNG2())
        sprite.texture.atlasTexture = uicore.uilib.CreateTexture(size, size)
        sprite.texture.atlasTexture.CopyFromSurface(surface)
        sprite.color.a = 1.0



    def Cache(self, imageid, mapitems, outsideitems):
        data = {'items': mapitems,
         'outsideitems': outsideitems,
         'areas': self.areas,
         'orbs': self.orbs,
         'sizefactor': self.sr.sizefactor,
         'sizefactorsize': self.sr.sizefactorsize,
         'cordsAsPortion': self.cordsAsPortion}
        settings.user.ui.Set('map2d_%s' % imageid, data)
        blue.pyos.synchro.Yield()



    def CheckIfCached(self, imageid):
        if settings.public.ui.Get('browsercacheversion', CACHEVERSION) != CACHEVERSION:
            util.DelTree(unicode(os.path.join(blue.os.cachepath, 'Temp/Mapbrowser')))
            settings.public.ui.Set('browsercacheversion', CACHEVERSION)
            return None
        return settings.user.ui.Get('map2d_%s' % imageid, None)



    def CheckMyLocation(self):
        if self is None or self.destroyed:
            return 
        self.updatemylocationtimer = None
        self.imhere.sr.x = self.imhere.sr.y = None
        self.imhere.state = uiconst.UI_HIDDEN
        self.destination.sr.x = self.destination.sr.y = None
        self.destination.state = uiconst.UI_HIDDEN
        destination = sm.GetService('starmap').GetDestination()
        if self.drawlevel < DRAWLVLSYS or eve.session.stationid:
            for locationID in self.cordsAsPortion.iterkeys():
                if locationID in self.MyHierarchy():
                    (self.imhere.sr.x, self.imhere.sr.y,) = self.cordsAsPortion[locationID]
                    self.imhere.state = uiconst.UI_DISABLED
                if destination and locationID == destination:
                    (self.destination.sr.x, self.destination.sr.y,) = self.cordsAsPortion[locationID]
                    self.destination.state = uiconst.UI_DISABLED

        elif self.ids[0] == eve.session.solarsystemid2:
            self.updatemylocationtimer = base.AutoTimer(100, self.UpdateMyLocation)
            uthread.new(self.UpdateMyLocation)
        self.RefreshOverlays(1)



    def UpdateMyLocation(self):
        if not uiutil.IsUnder(self, uicore.desktop):
            return 
        bp = sm.GetService('michelle').GetBallpark()
        if bp is None or self is None or self.destroyed:
            self.updatemylocationtimer = None
            return 
        myball = bp.GetBall(eve.session.shipid)
        if myball is None:
            self.updatemylocationtimer = None
            return 
        size = max(1, self.absoluteRight - self.absoluteLeft)
        if size == 1:
            uiutil.Update(self, 'Map2D::UpdateMyLocation')
            size = max(1, self.absoluteRight - self.absoluteLeft)
        x = y = None
        if self.allowAbstract and settings.user.ui.Get('solarsystemmapabstract', 0):
            if not len(self.orbs):
                return 
            (x, y,) = self.GetAbstractPosition(trinity.TriVector(myball.x, 0.0, myball.z), 1)
        elif self.sr.sizefactor is not None and self.sr.sizefactorsize is not None:
            maxdist = self.GetMaxDist()
            sizefactor = size / 2 / maxdist * self.fillSize
            x = FLIPMAP * myball.x * sizefactor / float(size) + 0.5
            y = -(myball.z * sizefactor) / float(size) + 0.5
        if x is not None and y is not None:
            self.imhere.sr.x = x
            self.imhere.sr.y = y
            self.imhere.state = uiconst.UI_DISABLED
        scene = sm.GetService('sceneManager').GetRegisteredScene('default')
        camera = sm.GetService('sceneManager').GetRegisteredCamera('default')
        rot = camera.rotationAroundParent.GetYawPitchRoll()
        look = camera.rotationOfInterest.GetYawPitchRoll()
        if not self.fov:
            self.fov = Fov(parent=self.imhere)
        self.fov.SetRotation(rot[0] + look[0] - pi)
        actualfov = camera.fieldOfView * (uicore.desktop.width / float(uicore.desktop.height))
        degfov = actualfov - pi / 2
        self.fov.SetFovAngle(actualfov)
        if self.showingtempangle:
            if not self.tempAngleFov:
                self.tempAngleFov = Fov(parent=self.imhere, state=uiconst.UI_DISABLED, blendMode=trinity.TR2_SBM_ADDX2)
                self.tempAngleFov.SetColor((0.0, 0.3, 0.0, 1.0))
            self.tempAngleFov.display = True
            self.tempAngleFov.SetRotation(rot[0] + look[0] - pi)
            angle = self.showingtempangle
            self.tempAngleFov.SetFovAngle(angle)
        elif self.tempAngleFov:
            self.tempAngleFov.display = False
        self.RefreshOverlays()



    def SetTempAngle(self, angle):
        if self.imhere is None or self.imhere.destroyed or len(self.imhere.children) <= 1:
            return 
        self.showingtempangle = angle



    def GetRegionColor(self, regionID):
        color = trinity.TriColor()
        color.SetHSV(float(regionID) * 21 % 360.0, 0.5, 0.8)
        color.a = 0.75
        return color



    def GetAbstractPosition(self, pos, asPortion = 0, size = None):
        if not len(self.orbs):
            return (None, None)
        dist = pos.Length()
        maxorb = None
        minorb = (0.0, 0)
        for (orbdist, pixelrad, orbititem, SIZE,) in self.orbs:
            if orbdist < dist:
                minorb = (orbdist, pixelrad)
            elif orbdist > dist and maxorb is None:
                maxorb = (orbdist, pixelrad)

        (mindist, minpixelrad,) = minorb
        distInPixels = minpixelrad
        if maxorb:
            (maxdist, maxpixelrad,) = maxorb
            rnge = maxdist - mindist
            pixelrnge = maxpixelrad - minpixelrad
            posWithinRange = dist - mindist
            distInPixels += pixelrnge * (posWithinRange / rnge)
        sizefactor = float(distInPixels) / dist
        if asPortion:
            size = max(1, self.absoluteRight - self.absoluteLeft)
            return (float(size) / (FLIPMAP * pos.x * sizefactor + SIZE / 2), float(size) / (pos.z * sizefactor + SIZE / 2))
        return (int(FLIPMAP * pos.x * sizefactor) + SIZE / 2, int(pos.z * sizefactor) + SIZE / 2)



    def GetPick(self):
        areas = []
        size = max(1, self.absoluteRight - self.absoluteLeft)
        radius = 2
        isAbstract = self.allowAbstract and settings.user.ui.Get('solarsystemmapabstract', 0) == 1
        for locationID in self.cordsAsPortion.iterkeys():
            if len(self.mouseHoverGroups) and not isAbstract:
                locationrec = self.GetItemRecord(locationID)[0]
                if not locationrec or locationrec.groupID not in self.mouseHoverGroups:
                    continue
            (x, y,) = self.GetCordsByKeyAsPortion(locationID, size)
            if x is None or y is None:
                continue
            if int(x - radius - 3) <= uicore.uilib.x - self.absoluteLeft <= int(x + radius + 3) and int(y - radius - 3) <= uicore.uilib.y - self.absoluteTop <= int(y + radius + 3):
                areas.append(locationID)

        return areas



    def GetItemRecord(self, getkey):
        for each in self.mapitems:
            if not hasattr(each, 'itemID'):
                continue
            if each.itemID == getkey:
                return (each, 1)

        for each in self.outsideitems:
            if not hasattr(each, 'itemID'):
                continue
            if each.itemID == getkey:
                return (each, 0)

        return (None, None)



    def GetCordsByKeyAsPortion(self, locationID, size = None):
        if size is None:
            return self.cordsAsPortion.get(locationID, (None, None))
        (x, y,) = self.cordsAsPortion.get(locationID, (None, None))
        if x is not None and y is not None:
            return (int(x * size), int(y * size))
        return (None, None)



    def ToggleAbstract(self, setTo):
        uthread.new(self._ToggleAbstract, setTo)



    def _ToggleAbstract(self, setTo):
        settings.user.ui.Set('solarsystemmapabstract', setTo)
        self.settings = None
        self.Draw(self.ids, self.idlevel, self.drawlevel, self.needsize)



    def SetSelected(self, ids):
        if self is None or self.destroyed:
            return 
        for each in self.overlays.children[:]:
            if each.name == 'selected':
                each.Close()

        for id in ids:
            (x, y,) = self.GetCordsByKeyAsPortion(id)
            if x is not None and y is not None:
                newsel = uicls.Container(parent=self.overlays, name='selected', align=uiconst.TOPLEFT, width=16, height=16, state=uiconst.UI_DISABLED)
                pointer = uicls.Sprite(parent=newsel, pos=(0, 0, 16, 32), state=uiconst.UI_PICKCHILDREN, texturePath='res:/UI/Texture/Shared/circlePointerDown.png', color=(1.0, 1.0, 1.0, 0.4))
                newsel.sr.x = x
                newsel.sr.y = y

        self.RefreshOverlays(1)



    def _OnResize(self):
        if self.align == uiconst.TOTOP:
            self.height = self.absoluteRight - self.absoluteLeft
        elif self.align in (uiconst.TOLEFT, uiconst.TORIGHT):
            self.width = self.absoluteBottom - self.absoluteTop
        try:
            self.RefreshOverlays(1)
        except:
            sys.exc_clear()



    def RefreshOverlays(self, update = 0):
        if not uiutil.IsUnder(self, uicore.desktop):
            return 
        if self is None or self.destroyed or not uicore.uilib:
            return 
        if update:
            uiutil.Update(self, 'Map2D::RefreshOverlays')
        size = self.absoluteRight - self.absoluteLeft
        for each in self.sr.areas.children:
            if not hasattr(each, 'sr') or getattr(each.sr, 'x', None) is None and getattr(each.sr, 'y', None) is None:
                continue
            each.width = each.height = int(each.sr.rad * size * 2)
            each.left = int(getattr(each.sr, 'x', 0) * size) - each.width / 2 + 1
            each.top = int(getattr(each.sr, 'y', 0) * size) - each.height / 2 + 1

        for each in self.overlays.children:
            if not hasattr(each, 'sr') or getattr(each.sr, 'x', None) is None and getattr(each.sr, 'y', None) is None:
                continue
            each.left = int(getattr(each.sr, 'x', 0) * size) - each.width / 2 + 1
            each.top = int(getattr(each.sr, 'y', 0) * size) - each.height / 2 + 1




    def OnClick(self, *args):
        areas = self.GetPick()
        if areas:
            self.OnSelectItem(self, areas[0])



    def OnMouseDown(self, *args):
        if self.dragAllowed:
            self.dragging = 1



    def OnMouseUp(self, *args):
        if self.dragging:
            self.left = max(-self.width + 24, min(self.parent.absoluteRight - self.parent.absoluteLeft - 24, self.left))
            self.top = max(-self.height + 24, min(self.parent.absoluteBottom - self.parent.absoluteTop - 24, self.top))
            uiutil.SetOrder(self, -1)
        self.dragging = 0



    def SetHint(self, hint):
        self.hilite.state = uiconst.UI_HIDDEN
        self.sr.hint = hint.replace('[ ', '').replace(' ]', '').strip()
        self.hilite.state = uiconst.UI_DISABLED



    def OnMouseMove(self, *args):
        if self.dragging:
            self.left = max(-self.width + 24, min(self.parent.absoluteRight - self.parent.absoluteLeft - 24, self.left))
            self.top = max(-self.height + 24, min(self.parent.absoluteBottom - self.parent.absoluteTop - 24, self.top))
            return 
        areas = self.GetPick()
        if areas:
            if (areas[0], len(areas)) == self.lasthilite:
                return 
            self.lasthilite = (areas[0], len(areas))
            (x, y,) = self.GetCordsByKeyAsPortion(areas[0], self.absoluteRight - self.absoluteLeft)
            if x is not None and y is not None:
                self.hilite.left = x - self.hilite.width / 2
                self.hilite.top = y - self.hilite.height / 2 + 1
                self.hilite.state = uiconst.UI_DISABLED
                locStr = ''
                for id in areas:
                    (datarec, datahint,) = self.GetDataArgs(id)
                    (item, insider,) = self.GetItemRecord(id)
                    if item:
                        groupname = cfg.invgroups.Get(item.groupID).name
                        if item.itemName.lower().find(groupname.lower()) >= 0:
                            groupname = ''
                        locStr += '%s %s%s<br>' % (item.itemName, groupname, datahint)
                        if not insider:
                            parent = sm.GetService('map').GetItem(item.locationID)
                            locStr = mls.UI_SHARED_MAPLINKTO % {'linkto': locStr[:-4],
                             'parent': parent.itemName,
                             'group': cfg.invgroups.Get(parent.groupID).name} + '<br>'

                if locStr[-4:] == '<br>':
                    locStr = locStr[:-4]
                self.SetHint(locStr)
                return 
        self.SetHint('')
        self.hilite.state = uiconst.UI_HIDDEN
        self.lasthilite = None



    def OnMouseExit(self, *args):
        self.hilite.state = uiconst.UI_HIDDEN



    def GetMenu(self):
        m = []
        pick = self.GetPick()
        if len(pick) == 1:
            (item, insider,) = self.GetItemRecord(pick[0])
            m += sm.GetService('menu').CelestialMenu(pick[0], item)
            m += self.GetDataMenu(pick[0])
        else:
            for itemID in pick:
                (item, insider,) = self.GetItemRecord(itemID)
                if item:
                    submenu = sm.GetService('menu').CelestialMenu(itemID, item)
                    submenu += self.GetDataMenu(itemID)
                    if len(submenu):
                        if item.groupID == const.groupStation:
                            locationName = uix.EditStationName(item.itemName)
                        else:
                            locationName = item.itemName
                        groupname = cfg.invgroups.Get(item.groupID).name
                        if locationName.lower().find(groupname.lower()) >= 0:
                            groupname = ''
                        locationName += ' %s' % groupname
                        m.append((locationName, submenu))

            m.sort()
        if not m:
            m = self.GetParentMenu()
        if self.drawlevel == DRAWLVLSYS:
            if self.allowAbstract:
                isAbstract = settings.user.ui.Get('solarsystemmapabstract', 0) == 1
                m += [None, ([mls.UI_SHARED_MAPSHOWABSTRACT, mls.UI_SHARED_MAPSHOWNONABSTRACT][isAbstract], self.ToggleAbstract, (not isAbstract,))]
        return m



    def GetParentMenu(self):
        return []



    def GetMaxDist(self):
        maxdist = 0.0
        for item in self.mapitems:
            pos = trinity.TriVector(item.x, 0.0, item.z)
            maxdist = max(maxdist, pos.Length())

        return maxdist



    def DrawSolarsystem(self, sprite, ids, imageid, mapitems, SIZE):
        if not len(mapitems):
            return 
        planets = []
        stargates = []
        asteroidbelts = []
        for item in mapitems:
            if item.groupID == const.groupPlanet:
                planets.append(item)
            elif item.groupID == const.groupStargate:
                stargates.append(item)
            elif item.groupID == const.groupAsteroidBelt:
                asteroidbelts.append(item)

        drawarea = DrawArea()
        drawarea.setTransparentColor(-1)
        drawarea.setSize(SIZE, SIZE, 4278190080L)
        cords = {}
        sunID = None
        maxdist = 0.0
        for item in mapitems:
            pos = trinity.TriVector(item.x, 0.0, item.z)
            maxdist = max(maxdist, pos.Length())
            if item.groupID == const.groupSun:
                sunID = item.itemID
                radius = 3
                drawarea.circle(SIZE / 2, SIZE / 2, radius, radius, 10066329, 10066329)

        sizefactor = SIZE / 2 / maxdist * self.fillSize
        self.sr.sizefactor = sizefactor
        self.sr.sizefactorsize = SIZE
        if self.allowAbstract and settings.user.ui.Get('solarsystemmapabstract', 0):
            _planets = []
            for planet in planets:
                pos = trinity.TriVector(planet.x, planet.y, planet.z)
                dist = pos.Length()
                _planets.append([dist, planet])

            _planets = uiutil.SortListOfTuples(_planets)
            planet = _planets
        i = 1
        for item in planets:
            pos = trinity.TriVector(item.x, 0.0, item.z)
            dist = pos.Length()
            if self.allowAbstract and settings.user.ui.Get('solarsystemmapabstract', 0):
                planetscale = i * (maxdist / len(planets)) / dist
                pos.Scale(planetscale)
            x = FLIPMAP * pos.x * sizefactor + SIZE / 2
            y = pos.z * sizefactor + SIZE / 2
            radius = 1
            cords[item.itemID] = (x, SIZE - y, radius)
            drawarea.circle(x, SIZE - y, radius, radius, 16777215, LtoI(4278190080L))
            self.AddChilds(x, y, radius, item.itemID, SIZE, drawarea, cords, item)
            i += 1

        self.orbs = []
        for orbit in planets:
            if orbit.itemID in cords:
                (x, y, radius,) = cords[orbit.itemID]
                center = SIZE / 2
                frompos = trinity.TriVector(float(center), 0.0, float(center))
                topos = trinity.TriVector(float(x), 0.0, float(y))
                diff = topos - frompos
                rad = int(diff.Length())
                drawarea.circle(center, center, rad, rad, self.GetColorByGroupID(const.groupPlanet), LtoI(4278190080L))
                orbpos = trinity.TriVector(orbit.x, 0.0, orbit.z)
                orbdist = orbpos.Length()
                self.orbs.append([orbdist, (orbdist,
                  rad,
                  orbit,
                  SIZE)])

        self.orbs = uiutil.SortListOfTuples(self.orbs)
        for item in stargates:
            if self.allowAbstract and settings.user.ui.Get('solarsystemmapabstract', 0):
                if not len(self.orbs):
                    return 
                (x, y,) = self.GetAbstractPosition(trinity.TriVector(item.x, 0.0, item.z))
            else:
                x = FLIPMAP * self.sr.sizefactor * item.x + self.sr.sizefactorsize / 2
                y = self.sr.sizefactor * item.z + self.sr.sizefactorsize / 2
            x += 6
            radius = 1
            drawarea.circle(x, SIZE - y, radius, radius, 0, self.GetColorByGroupID(const.groupStargate))
            cords[item.itemID] = (x, SIZE - y, radius)

        self.areas = [ (cords[id][0],
         cords[id][1],
         cords[id][2],
         id) for id in cords.iterkeys() ]
        self.cordsAsPortion = {}
        for id in cords.iterkeys():
            self.cordsAsPortion[id] = (cords[id][0] / float(SIZE), cords[id][1] / float(SIZE))

        self.Cache(imageid, mapitems, [])
        if self.destroyed:
            return 
        self.PlaceBackground('res:/UI/Texture/map_ssunderlay.png')
        self.PlaceMap(sprite, drawarea, SIZE)



    def AddChilds(self, parentX, parentY, parentRad, parentID, SIZE, draw, cords, parent, _x = None, _y = None):
        parentpos = trinity.TriVector(parent.x, parent.y, parent.z)
        sorted = []
        allchilds = self.GetChilds(parentID, [], 0)
        for child in allchilds:
            childpos = trinity.TriVector(child.x, child.y, child.z)
            diff = childpos - parentpos
            dist = diff.Length()
            sorted.append((dist, child))

        sorted = uiutil.SortListOfTuples(sorted)
        if self.allowAbstract and settings.user.ui.Get('solarsystemmapabstract', 0):
            done = []
            i = 1
            xi = 0
            for child in sorted:
                if child.itemID in done:
                    continue
                radius = 1
                step = max(12, radius * 4) - 2
                y = _y or parentY + parentRad + i * step
                x = _x or parentX + xi
                if y + step > SIZE:
                    i = 0
                    xi += step
                done.append(child.itemID)
                fill = self.GetColorByGroupID(child.groupID)
                draw.circle(x, SIZE - y, radius, radius, fill, fill)
                cords[child.itemID] = (x, SIZE - y, radius)
                i += 1

        else:
            for child in sorted:
                radius = 1
                pos = trinity.TriVector(child.x, 0.0, child.z)
                pos = pos + (pos - parentpos) * max(1.0, 4096 / SIZE)
                x = FLIPMAP * pos.x * self.sr.sizefactor + SIZE / 2
                y = pos.z * self.sr.sizefactor + SIZE / 2
                fill = self.GetColorByGroupID(child.groupID)
                draw.circle(x, SIZE - y, radius, radius, fill, fill)
                cords[child.itemID] = (x, SIZE - y, radius)




    def GetChilds(self, parentID, childs, i):
        i += 1
        if i == 20 or len(childs) > 1000:
            return childs
        _childs = [ child for child in self.mapitems if child.orbitID == parentID if child not in childs ]
        if len(_childs):
            childs += _childs
            for granchild in _childs:
                childs = self.GetChilds(granchild.itemID, childs, i)

        return childs



    def GetColorByGroupID(self, groupID):
        col = {const.groupAsteroidBelt: 255,
         const.groupPlanet: 8947848,
         const.groupStargate: 34816,
         const.groupStation: 16724787}.get(groupID, 10066329)
        return col



    def GetDataArgs(self, locationID):
        if locationID in self.dataArgs:
            return self.dataArgs[locationID]
        return (None, '')



    def GetDataMenu(self, locationID):
        (datarec, datahint,) = self.GetDataArgs(locationID)
        if not datarec:
            return []
        locationrec = self.GetItemRecord(locationID)[0]
        if not locationrec:
            return []
        return self.GetDataMenuExt(self, locationrec, datarec)



    def GetDataMenuExt(self, *args):
        return []



    def Fade(self, what, f, t):
        (start, ndt,) = (blue.os.GetTime(), 0.0)
        while ndt != 1.0:
            ndt = min(blue.os.TimeDiffInMs(start) / 1000.0, 1.0)
            what.color.a = mathUtil.Lerp(f, t, ndt)
            blue.pyos.synchro.Yield()




    def PlaceBackground(self, imagepath):
        if self is None or self.destroyed:
            return 
        imagepath = str(imagepath)
        if self.bgSprite is None:
            self.bgSprite = uicls.Sprite(name='bgSprite', parent=self, align=uiconst.TOALL, state=uiconst.UI_DISABLED, color=(1.0, 1.0, 1.0, 1.0), texturePath=imagepath, filter=True)



    def OnSelectItem(self, _self, arg, *args):
        pass




class Fov(uicls.Transform):
    __guid__ = 'uicls.Map2dFov'
    default_name = 'fov'
    default_left = 0
    default_top = 0
    default_width = 128
    default_height = 128
    default_align = uiconst.CENTER
    default_state = uiconst.UI_NORMAL

    def ApplyAttributes(self, attributes):
        uicls.Transform.ApplyAttributes(self, attributes)
        blendMode = attributes.get('blendMode', trinity.TR2_SBM_BLEND)
        self.angle = math.pi
        self.color = (1.0, 1.0, 1.0, 0.5)
        self.polygon = uicls.Polygon(parent=self, align=uiconst.TOALL, blendMode=trinity.TR2_SBM_ADD)
        self.RenderGradient()



    def RenderGradient(self):
        self.polygon.Flush()
        directionAngle = math.pi / 2
        fromDeg = directionAngle - self.angle / 2
        toDeg = directionAngle + self.angle / 2
        numSegments = 40
        segmentStep = (toDeg - fromDeg) / float(numSegments)
        c = self.color
        innerColor = c
        outerColor = (c[0],
         c[1],
         c[2],
         0.0)
        radius = 50
        ro = self.polygon.GetRenderObject()
        for i in xrange(numSegments + 1):
            a = fromDeg + i * segmentStep
            x = math.cos(a)
            y = -math.sin(a)
            innerVertex = trinity.Tr2Sprite2dVertex()
            innerVertex.position = (self.width / 2, self.height / 2)
            innerVertex.color = innerColor
            ro.vertices.append(innerVertex)
            outerVertex = trinity.Tr2Sprite2dVertex()
            outerVertex.position = (self.width / 2 + radius * x, self.height / 2 + radius * y)
            outerVertex.color = outerColor
            ro.vertices.append(outerVertex)

        for i in xrange(numSegments * 2):
            triangle = trinity.Tr2Sprite2dTriangle()
            triangle.index0 = i
            triangle.index1 = i + 1
            triangle.index2 = i + 2
            ro.triangles.append(triangle)




    def SetColor(self, color):
        self.color = color
        self.RenderGradient()



    def SetFovAngle(self, angle):
        self.angle = angle
        self.RenderGradient()




