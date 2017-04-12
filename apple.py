#!/usr/bin/python
# vim:ts=4 sts=4 sw=4 expandtab

"""apple.py

Manages and launches iOS applications on device.

This is primarily intended to be used to run automated smoke tests of iOS
applications on non-jailbroken iOS devices.

See "apple.py -h" for usage.

A typical automated test might execute something like follow, to uninstall any
old versions of the app (-u), install the new one (-m), mount the developer
disk image (-m), run the app (-r), and pass the arguments "--smokeTest" to the
app (-a).
    apple.py -b build/Example.app -u -i -m -r -a --smokeTest

This will display all output from the app to standard out as it is running and
exit with the application's exit code.
"""

__author__ = 'Cory McWilliams <cory@unprompted.com>'
__version__ = "1.0.0"

__license__ = """
Copyright (c) 2013 Cory McWilliams <cory@unprompted.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

__credits__ = """
Made possible by:
1. fruitstrap from Greg Hughes: <https://github.com/ghughes/fruitstrap.git>
   Why didn't Apple just write this and save us all time?
2. idevice-app-runner for demonstrating that you don't need gdb to talk to
   debugserver: <https://github.com/crackleware/idevice-app-runner.git>
3. libimobiledevice for demonstrating how to make penguins talk to fruits:
   <http://www.libimobiledevice.org/>
"""

import argparse
import ctypes
import ctypes.macholib.dyld
import ctypes.util
import os
import plistlib
import socket
import subprocess
import sys
import struct
import time

# CoreFoundation.framework

if sys.platform == 'win32':
    os.environ['PATH'] += os.pathsep + os.path.join(os.environ['CommonProgramFiles'], 'Apple', 'Apple Application Support')
    CoreFoundation = ctypes.CDLL('CoreFoundation.dll')
else:
    CoreFoundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')

CFShow = CoreFoundation.CFShow
CFShow.argtypes = [ctypes.c_void_p]
CFShow.restype = None

CFGetTypeID = CoreFoundation.CFGetTypeID
CFGetTypeID.argtypes = [ctypes.c_void_p]
CFGetTypeID.restype = ctypes.c_ulong

CFStringRef = ctypes.c_void_p

CFStringGetTypeID = CoreFoundation.CFStringGetTypeID
CFStringGetTypeID.argtypes = []
CFStringGetTypeID.restype = ctypes.c_ulong

CFDictionaryGetTypeID = CoreFoundation.CFDictionaryGetTypeID
CFDictionaryGetTypeID.argtypes = []
CFDictionaryGetTypeID.restype = ctypes.c_ulong

CFStringGetLength = CoreFoundation.CFStringGetLength
CFStringGetLength.argtypes = [CFStringRef]
CFStringGetLength.restype = ctypes.c_ulong

CFCopyDescription = CoreFoundation.CFCopyDescription
CFCopyDescription.argtypes = [ctypes.c_void_p]
CFCopyDescription.restype = CFStringRef

CFNumberGetValue = CoreFoundation.CFNumberGetValue
CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p]
CFNumberGetValue.restype = ctypes.c_bool

kCFNumberSInt32Type = 3

CFRunLoopRun = CoreFoundation.CFRunLoopRun
CFRunLoopRun.argtypes = []
CFRunLoopRun.restype = None

CFRunLoopStop = CoreFoundation.CFRunLoopStop
CFRunLoopStop.argtypes = [ctypes.c_void_p]
CFRunLoopStop.restype = None

CFRunLoopGetCurrent = CoreFoundation.CFRunLoopGetCurrent
CFRunLoopGetCurrent.argtype = []
CFRunLoopGetCurrent.restype = ctypes.c_void_p

cf_run_loop_timer_callback = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)

CFRunLoopTimerCreate = CoreFoundation.CFRunLoopTimerCreate
CFRunLoopTimerCreate.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double, ctypes.c_uint, ctypes.c_uint, cf_run_loop_timer_callback, ctypes.c_void_p]
CFRunLoopTimerCreate.restype = ctypes.c_void_p

kCFRunLoopCommonModes = CFStringRef.in_dll(CoreFoundation, 'kCFRunLoopCommonModes')

CFAbsoluteTimeGetCurrent = CoreFoundation.CFAbsoluteTimeGetCurrent
CFAbsoluteTimeGetCurrent.argtypes = []
CFAbsoluteTimeGetCurrent.restype = ctypes.c_double

CFRunLoopAddTimer = CoreFoundation.CFRunLoopAddTimer
CFRunLoopAddTimer.argtypes = [ctypes.c_void_p, ctypes.c_void_p, CFStringRef]
CFRunLoopAddTimer.restype = None

CFRunLoopRemoveTimer = CoreFoundation.CFRunLoopRemoveTimer
CFRunLoopRemoveTimer.argtypes = [ctypes.c_void_p, ctypes.c_void_p, CFStringRef]
CFRunLoopRemoveTimer.restype = None

CFDictionaryRef = ctypes.c_void_p

class CFDictionaryKeyCallBacks(ctypes.Structure):
    _fields_ = [
        ('version', ctypes.c_uint),
        ('retain', ctypes.c_void_p),
        ('release', ctypes.c_void_p),
        ('copyDescription', ctypes.c_void_p),
        ('equal', ctypes.c_void_p),
        ('hash', ctypes.c_void_p),
    ]

class CFDictionaryValueCallBacks(ctypes.Structure):
    _fields_ = [
        ('version', ctypes.c_uint),
        ('retain', ctypes.c_void_p),
        ('release', ctypes.c_void_p),
        ('copyDescription', ctypes.c_void_p),
        ('equal', ctypes.c_void_p),
    ]

CFDictionaryCreate = CoreFoundation.CFDictionaryCreate
CFDictionaryCreate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.POINTER(CFDictionaryKeyCallBacks), ctypes.POINTER(CFDictionaryValueCallBacks)]
CFDictionaryCreate.restype = CFDictionaryRef

CFDictionaryGetValue = CoreFoundation.CFDictionaryGetValue
CFDictionaryGetValue.argtypes = [CFDictionaryRef, CFStringRef]
CFDictionaryGetValue.restype = ctypes.c_void_p

CFDictionaryGetCount = CoreFoundation.CFDictionaryGetCount
CFDictionaryGetCount.argtypes = [CFDictionaryRef]
CFDictionaryGetCount.restype = ctypes.c_int

CFDictionaryGetKeysAndValues = CoreFoundation.CFDictionaryGetKeysAndValues
CFDictionaryGetKeysAndValues.argtypes = [CFDictionaryRef, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
CFDictionaryGetKeysAndValues.restype = None

kCFTypeDictionaryKeyCallBacks = CFDictionaryKeyCallBacks.in_dll(CoreFoundation, 'kCFTypeDictionaryKeyCallBacks')
kCFTypeDictionaryValueCallBacks = CFDictionaryValueCallBacks.in_dll(CoreFoundation, 'kCFTypeDictionaryValueCallBacks')

CFDataRef = ctypes.c_void_p
CFDataCreate = CoreFoundation.CFDataCreate
CFDataCreate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
CFDataCreate.restype = ctypes.c_void_p

CFStringCreateWithCString = CoreFoundation.CFStringCreateWithCString
CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint]
CFStringCreateWithCString.restype = CFStringRef

def CFStr(value):
    return CFStringCreateWithCString(None, value, kCFStringEncodingUTF8)

CFStringGetCStringPtr = CoreFoundation.CFStringGetCStringPtr
CFStringGetCStringPtr.argtypes = [CFStringRef, ctypes.c_uint]
CFStringGetCStringPtr.restype = ctypes.c_char_p

CFStringGetCString = CoreFoundation.CFStringGetCString
CFStringGetCString.argtypes = [CFStringRef, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint]
CFStringGetCString.restype = ctypes.c_bool

kCFStringEncodingUTF8 = 0x08000100

def CFStringGetStr(cfstr):
    result = None
    if cfstr:
        result = CFStringGetCStringPtr(cfstr, kCFStringEncodingUTF8)
        if not result:
            length = CFStringGetLength(cfstr) * 2 + 1
            stringBuffer = ctypes.create_string_buffer(length)
            if CFStringGetCString(cfstr, stringBuffer, length, kCFStringEncodingUTF8):
                result = stringBuffer.value
            else:
                raise RuntimeError('Failed to convert string.')
    return result

def CFDictionaryToDict(dictionary):
    count = CFDictionaryGetCount(dictionary)
    keys = (ctypes.c_void_p * count)()
    values = (ctypes.c_void_p * count)()
    CFDictionaryGetKeysAndValues(dictionary, keys, values)
    keys = [CFToPython(key) for key in keys]
    values = [CFToPython(value) for value in values]
    return dict(zip(keys, values))

def CFToPython(dataRef):
    typeId = CFGetTypeID(dataRef)
    if typeId == CFStringGetTypeID():
        return CFStringGetStr(dataRef)
    elif typeId == CFDictionaryGetTypeID():
        return CFDictionaryToDict(dataRef)
    else:
        description = CFCopyDescription(dataRef)
        return CFStringGetStr(description)

# MobileDevice.Framework

if sys.platform == 'win32':
    os.environ['PATH'] += os.pathsep + os.path.join(os.environ['CommonProgramFiles'], 'Apple', 'Mobile Device Support')
    MobileDevice = ctypes.CDLL('MobileDevice.dll')
else:
    MobileDevice = ctypes.CDLL('/System/Library/PrivateFrameworks/MobileDevice.framework/MobileDevice')

AMDSetLogLevel = MobileDevice.AMDSetLogLevel
AMDSetLogLevel.argtypes = [ctypes.c_int]
AMDSetLogLevel.restype = None

AMDSetLogLevel(5)

am_device_p = ctypes.c_void_p

class am_device_notification(ctypes.Structure):
    pass

class am_device_notification_callback_info(ctypes.Structure):
    _fields_ = [
        ('dev', am_device_p),
        ('msg', ctypes.c_uint),
        ('subscription', ctypes.POINTER(am_device_notification)),
    ]

am_device_notification_callback = ctypes.CFUNCTYPE(None, ctypes.POINTER(am_device_notification_callback_info), ctypes.c_int)

am_device_notification._fields_ = [
    ('unknown0', ctypes.c_uint),
    ('unknown1', ctypes.c_uint),
    ('unknown2', ctypes.c_uint),
    ('callback', ctypes.c_void_p),
    ('cookie', ctypes.c_uint),
]

am_device_notification_p = ctypes.POINTER(am_device_notification)

AMDeviceNotificationSubscribe = MobileDevice.AMDeviceNotificationSubscribe
AMDeviceNotificationSubscribe.argtypes = [am_device_notification_callback, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
AMDeviceNotificationSubscribe.restype = ctypes.c_uint

AMDeviceNotificationUnsubscribe = MobileDevice.AMDeviceNotificationUnsubscribe
AMDeviceNotificationUnsubscribe.argtypes = [ctypes.c_void_p]
AMDeviceNotificationUnsubscribe.restype = ctypes.c_uint

ADNCI_MSG_CONNECTED = 1
ADNCI_MSG_DISCONNECTED = 2
ADNCI_MSG_UNKNOWN = 3

AMDeviceCopyValue = MobileDevice.AMDeviceCopyValue
AMDeviceCopyValue.argtypes = [am_device_p, CFStringRef, CFStringRef]
AMDeviceCopyValue.restype = CFStringRef

AMDeviceGetConnectionID = MobileDevice.AMDeviceGetConnectionID
AMDeviceGetConnectionID.argtypes = [am_device_p]
AMDeviceGetConnectionID.restype = ctypes.c_uint

AMDeviceCopyDeviceIdentifier = MobileDevice.AMDeviceCopyDeviceIdentifier
AMDeviceCopyDeviceIdentifier.argtypes = [am_device_p]
AMDeviceCopyDeviceIdentifier.restype = CFStringRef

AMDeviceConnect = MobileDevice.AMDeviceConnect
AMDeviceConnect.argtypes = [am_device_p]
AMDeviceConnect.restype = ctypes.c_uint

AMDevicePair = MobileDevice.AMDevicePair
AMDevicePair.argtypes = [am_device_p]
AMDevicePair.restype = ctypes.c_uint

AMDeviceIsPaired = MobileDevice.AMDeviceIsPaired
AMDeviceIsPaired.argtypes = [am_device_p]
AMDeviceIsPaired.restype = ctypes.c_uint

AMDeviceValidatePairing = MobileDevice.AMDeviceValidatePairing
AMDeviceValidatePairing.argtypes = [am_device_p]
AMDeviceValidatePairing.restype = ctypes.c_uint

AMDeviceStartSession = MobileDevice.AMDeviceStartSession
AMDeviceStartSession.argtypes = [am_device_p]
AMDeviceStartSession.restype = ctypes.c_uint

AMDeviceStopSession = MobileDevice.AMDeviceStopSession
AMDeviceStopSession.argtypes = [am_device_p]
AMDeviceStopSession.restype = ctypes.c_uint

AMDeviceDisconnect = MobileDevice.AMDeviceDisconnect
AMDeviceDisconnect.argtypes = [am_device_p]
AMDeviceDisconnect.restype = ctypes.c_uint

am_device_mount_image_callback = ctypes.CFUNCTYPE(ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)

try:
    AMDeviceMountImage = MobileDevice.AMDeviceMountImage
    AMDeviceMountImage.argtypes = [am_device_p, CFStringRef, CFDictionaryRef, am_device_mount_image_callback, ctypes.c_void_p]
    AMDeviceMountImage.restype = ctypes.c_uint
except AttributeError:
    # AMDeviceMountImage is missing on win32.
    AMDeviceMountImage = None

AMDeviceStartService = MobileDevice.AMDeviceStartService
AMDeviceStartService.argtypes = [am_device_p, CFStringRef, ctypes.POINTER(ctypes.c_int), ctypes.c_void_p]
AMDeviceStartService.restype = ctypes.c_uint

AMDeviceStartHouseArrestService = MobileDevice.AMDeviceStartHouseArrestService
AMDeviceStartHouseArrestService.argtypes = [am_device_p, CFStringRef, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_void_p]
AMDeviceStartHouseArrestService.restype = ctypes.c_uint

am_device_install_application_callback = ctypes.CFUNCTYPE(ctypes.c_uint, CFDictionaryRef, ctypes.c_void_p)

AMDeviceTransferApplication = MobileDevice.AMDeviceTransferApplication
AMDeviceTransferApplication.argtypes = [ctypes.c_int, CFStringRef, CFDictionaryRef, am_device_install_application_callback, ctypes.c_void_p]
AMDeviceTransferApplication.restype = ctypes.c_uint

AMDeviceInstallApplication = MobileDevice.AMDeviceInstallApplication
AMDeviceInstallApplication.argtypes = [ctypes.c_int, CFStringRef, CFDictionaryRef, am_device_install_application_callback, ctypes.c_void_p]
AMDeviceInstallApplication.restype = ctypes.c_uint

AMDeviceUninstallApplication = MobileDevice.AMDeviceUninstallApplication
AMDeviceUninstallApplication.argtypes = [ctypes.c_int, CFStringRef, CFDictionaryRef, am_device_install_application_callback, ctypes.c_void_p]
AMDeviceUninstallApplication.restype = ctypes.c_uint

AMDeviceLookupApplications = MobileDevice.AMDeviceLookupApplications
AMDeviceLookupApplications.argtypes = [am_device_p, ctypes.c_uint, ctypes.POINTER(CFDictionaryRef)]
AMDeviceLookupApplications.restype = ctypes.c_uint

# AFC

AFCConnectionRef = ctypes.c_void_p
AFCFileRef = ctypes.c_ulonglong

AFCConnectionOpen = MobileDevice.AFCConnectionOpen
AFCConnectionOpen.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(AFCConnectionRef)]
AFCConnectionOpen.restype = ctypes.c_uint

AFCConnectionClose = MobileDevice.AFCConnectionClose
AFCConnectionClose.argtypes = [AFCConnectionRef]
AFCConnectionClose.restype = ctypes.c_uint

AFCFileRefOpen = MobileDevice.AFCFileRefOpen
AFCFileRefOpen.argtypes = [AFCConnectionRef, ctypes.c_char_p, ctypes.c_ulonglong, ctypes.POINTER(AFCFileRef)]
AFCFileRefOpen.restype = ctypes.c_uint

AFCFileRefRead = MobileDevice.AFCFileRefRead
AFCFileRefRead.argtypes = [AFCConnectionRef, AFCFileRef, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
AFCFileRefRead.restype = ctypes.c_uint

AFCFileRefWrite = MobileDevice.AFCFileRefWrite
AFCFileRefWrite.argtypes = [AFCConnectionRef, AFCFileRef, ctypes.c_void_p, ctypes.c_uint]
AFCFileRefWrite.restype = ctypes.c_uint

AFCFileRefClose = MobileDevice.AFCFileRefClose
AFCFileRefClose.argtypes = [AFCConnectionRef, AFCFileRef]
AFCFileRefClose.restype = ctypes.c_uint

AFCDirectoryCreate = MobileDevice.AFCDirectoryCreate
AFCDirectoryCreate.argtypes = [AFCConnectionRef, ctypes.c_char_p]
AFCDirectoryCreate.restype = ctypes.c_uint

AFCRemovePath = MobileDevice.AFCRemovePath
AFCRemovePath.argtypes = [AFCConnectionRef, ctypes.c_char_p]
AFCRemovePath.restype = ctypes.c_uint

AFCDirectoryRef = ctypes.c_void_p

AFCDirectoryOpen = MobileDevice.AFCDirectoryOpen
AFCDirectoryOpen.argtypes = [AFCConnectionRef, ctypes.c_char_p, ctypes.POINTER(AFCDirectoryRef)]
AFCDirectoryOpen.restype = ctypes.c_uint

AFCDirectoryRead = MobileDevice.AFCDirectoryRead
AFCDirectoryRead.argtypes = [AFCConnectionRef, AFCDirectoryRef, ctypes.POINTER(ctypes.c_char_p)]
AFCDirectoryRead.restype = ctypes.c_uint

AFCDirectoryClose = MobileDevice.AFCDirectoryClose
AFCDirectoryClose.argtypes = [AFCConnectionRef, AFCDirectoryRef]
AFCDirectoryClose.restype = ctypes.c_uint

# ws2_32.dll

if sys.platform == 'win32':
    ws2_32 = ctypes.WinDLL('ws2_32.dll')

    socket_close = ws2_32.closesocket
    socket_close.argtypes = [ctypes.c_uint]
    socket_close.restype = ctypes.c_int

    socket_recv = ws2_32.recv
    socket_recv.argtypes = [ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    socket_recv.restype = ctypes.c_int

    socket_send = ws2_32.send
    socket_send.argtypes = [ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    socket_send.restype = ctypes.c_int

    socket_setsockopt = ws2_32.setsockopt
    socket_setsockopt.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    socket_setsockopt.restype = ctypes.c_int

    SOL_SOCKET = 0xffff
    SO_SNDTIMEO = 0x1005
    SO_RCVTIMEO = 0x1006

    class MockSocket(object):
        """
        Python doesn't provide a way to get a socket-like object from a socket
        descriptor, so this implements just enough of the interface for what we
        need.
        """

        def __init__(self, socketDescriptor):
            self._socket = socketDescriptor

        def send(self, data):
            return socket_send(self._socket, data, len(data), 0)

        def sendall(self, data):
            while data:
                result = self.send(data)
                if result < 0:
                    raise RuntimeError('Error sending data: %d' % result)
                data = data[result:]

        def recv(self, bytes):
            data = ctypes.create_string_buffer(bytes)
            result = socket_recv(self._socket, data, bytes, 0)
            if result < 0:
                raise RuntimeError('Error receiving data: %d' % result)
            return data.raw[:result]

        def close(self):
            socket_close(self._socket)
            self._socket = None

        def settimeout(self, timeout):
            ms = int(timeout * 1000)
            value = ctypes.c_int(ms)
            e = socket_setsockopt(self._socket, SOL_SOCKET, SO_SNDTIMEO, ctypes.byref(value), 4)
            if e != 0:
                raise RuntimeError('setsockopt returned %d' % e)
            e = socket_setsockopt(self._socket, SOL_SOCKET, SO_RCVTIMEO, ctypes.byref(value), 4)
            if e != 0:
                raise RuntimeError('setsockopt returned %d' % e)

class RawPlistService(object):
    def __init__(self, service):
        if sys.platform == 'win32':
            self._socket = MockSocket(service)
        else:
            self._socket = socket.fromfd(service, socket.AF_INET, socket.SOCK_STREAM)

    def close(self):
        self._socket.close()

    def exchange(self, data):
        payload = plistlib.writePlistToString(data).encode('utf-8')
        message = struct.pack('>i', len(payload)) + payload
        self._socket.sendall(message)

        header = self._socket.recv(4)
        size = struct.unpack('>i', header)[0]
        payload = self._socket.recv(size)
        return plistlib.readPlistFromString(payload)

# Finally, the good stuff.

class MobileDeviceManager(object):
    """
    Presents interesting parts of Apple's MobileDevice framework as a much more
    Python-friendly way.

    Usage is generally like this:
        mdm = MobileDeviceManager()
        mdm.waitForDevice()
        mdm.connect()

        # do things with the connected device...
        mdm.installApplication('build/MyApp.app')

        mdm.disconnect()
        mdm.close()
    """

    def __init__(self):
        self._device = None
        self._waitForDeviceId = None
        self._notification = None

        self._transferCallback = am_device_install_application_callback(self._transfer)
        self._installCallback = am_device_install_application_callback(self._install)
        self._uninstallCallback = am_device_install_application_callback(self._uninstall)
        self._timerCallback = cf_run_loop_timer_callback(self._timer)

    def close(self):
        if self._device:
            self._device = None
        if self._notification:
            AMDeviceNotificationUnsubscribe(self._notification)
            self._notification = None

    def connect(self):
        e = AMDeviceConnect(self._device)
        if e != 0:
            raise RuntimeError('AMDeviceConnect returned %d' % e)

        if not self.isPaired():
            self.pair()
        self.validatePairing()

    def disconnect(self):
        e = AMDeviceDisconnect(self._device)
        if e != 0:
            raise RuntimeError('AMDeviceDisconnect returned %d' % e)

    def pair(self):
        e = AMDevicePair(self._device)
        if e != 0:
            raise RuntimeError('AMDevicePair returned %d' % e)

    def isPaired(self):
        return AMDeviceIsPaired(self._device) != 0

    def validatePairing(self):
        e = AMDeviceValidatePairing(self._device)
        if e != 0:
            raise RuntimeError('AMDeviceValidatePairing returned %d' % e)

    def startSession(self):
        e = AMDeviceStartSession(self._device)
        if e != 0:
            raise RuntimeError('AMDeviceStartSession returned %d' % e)

    def stopSession(self):
        e = AMDeviceStopSession(self._device)
        if e != 0:
            raise RuntimeError('AMDeviceStopSession returned %d' % e)

    def waitForDevice(self, timeout=0, device=None):
        self._waitForDeviceId = device
        self._notification = ctypes.c_void_p()
        self._notificationCallback = am_device_notification_callback(self._deviceNotification)
        e = AMDeviceNotificationSubscribe(self._notificationCallback, 0, 0, 0, ctypes.byref(self._notification))
        if e != 0:
            raise RuntimeError('AMDeviceNotificationSubscribe returned %d' % e)

        if timeout > 0:
            timer = CFRunLoopTimerCreate(None, CFAbsoluteTimeGetCurrent() + timeout, 0, 0, 0, self._timerCallback, None)
            CFRunLoopAddTimer(CFRunLoopGetCurrent(), timer, kCFRunLoopCommonModes)

        CFRunLoopRun()
        if timeout > 0:
            CFRunLoopRemoveTimer(CFRunLoopGetCurrent(), timer, kCFRunLoopCommonModes)
        return self._device

    def productVersion(self):
        self.connect()
        try:
            return CFStringGetStr(AMDeviceCopyValue(self._device, None, CFStr("ProductVersion")))
        finally:
            self.disconnect()

    def buildVersion(self):
        self.connect()
        try:
            return CFStringGetStr(AMDeviceCopyValue(self._device, None, CFStr("BuildVersion")))
        finally:
            self.disconnect()

    def connectionId(self):
        return AMDeviceGetConnectionID(self._device)

    def deviceId(self):
        return CFStringGetStr(AMDeviceCopyDeviceIdentifier(self._device))

    def mountImage(self, imagePath):
        if sys.platform == 'win32':
            imageMounterService = self.startService('com.apple.mobile.mobile_image_mounter')
            try:
                # AMDeviceMountImage isn't exported in MobileDevice.dll grumble grumble.
                raw = RawPlistService(imageMounterService)

                result = raw.exchange({
                    'Command': 'ReceiveBytes',
                    'ImageSize': os.stat(imagePath).st_size,
                    'ImageType': 'Developer',
                    'ImageSignature': plistlib.Data(open(imagePath + '.signature', 'rb').read()),
                })
                if result.get('Status') == 'ReceiveBytesAck':
                    # Only supported by iOS 7 and up?
                    raw._socket.sendall(open(imagePath, 'rb').read())
                else:
                    service = self.startService('com.apple.afc')
                    try:
                        afc = AFC(service)
                        try:
                            afc.mkdir('PublicStaging')
                            target = afc.open('PublicStaging/staging.dimage', 'w')
                            with open(imagePath, 'rb') as source:
                                while True:
                                    data = source.read(8192)
                                    if data:
                                        target.write(data)
                                    else:
                                        break
                            target.close()
                        finally:
                            afc.close()
                    finally:
                        self.stopService(service)

                result = raw.exchange({
                    'Command': 'MountImage',
                    'ImageType': 'Developer',
                    'ImageSignature': plistlib.Data(open(imagePath + '.signature', 'rb').read()),
                    'ImagePath': '/var/mobile/Media/PublicStaging/staging.dimage',
                })
                if 'Error' in result:
                    print 'MountImage returned', result['Error']
                if 'Status' in result:
                    print 'MountImage =>', result['Status']
            finally:
                self.stopService(imageMounterService)
        else:
            self.connect()
            try:
                self.startSession()
                try:
                    signature = open(imagePath + '.signature', 'rb').read()
                    signature = CFDataCreate(None, signature, len(signature))
                    items = 2

                    keys = (ctypes.c_void_p * items)(CFStr('ImageSignature'), CFStr('ImageType'))
                    values = (ctypes.c_void_p * items)(signature, CFStr('Developer'))

                    options = CFDictionaryCreate(None, keys, values, items, ctypes.byref(kCFTypeDictionaryKeyCallBacks), ctypes.byref(kCFTypeDictionaryValueCallBacks))
                    self._mountCallback = am_device_mount_image_callback(self._mount)
                    e = AMDeviceMountImage(self._device, CFStr(imagePath), options, self._mountCallback, None)
                    if e == 0:
                        return True
                    elif e  == 0xe8000076:
                        # already mounted
                        return False
                    else:
                        raise RuntimeError('AMDeviceMountImage returned %d' % e)
                finally:
                    self.stopSession()
            finally:
                self.disconnect()

    def startService(self, service):
        self.connect()
        try:
            self.startSession()
            try:
                fd = ctypes.c_int()
                e = AMDeviceStartService(self._device, CFStr(service), ctypes.byref(fd), None)
                if e != 0:
                    raise RuntimeError('AMDeviceStartService returned %d' % e)
                return fd.value
            finally:
                self.stopSession()
        finally:
            self.disconnect()

    def startHouseArrestService(self, bundleId):
        self.connect()
        try:
            self.startSession()
            try:
                fd = ctypes.c_int()
                e = AMDeviceStartHouseArrestService(self._device, CFStr(bundleId), None, ctypes.byref(fd), None)
                if e != 0:
                    raise RuntimeError('AMDeviceStartHouseArrestService returned %d' % e)
                return fd.value
            finally:
                self.stopSession()
        finally:
            self.disconnect()

    def bundleId(self, path):
        plist = plistlib.readPlist(os.path.join(path, 'Info.plist'))
        return plist['CFBundleIdentifier']

    def bundleExecutable(self, path):
        plist = plistlib.readPlist(os.path.join(path, 'Info.plist'))
        return plist['CFBundleExecutable']

    def transferApplication(self, path):
        afc = self.startService("com.apple.afc")
        try:
            e = AMDeviceTransferApplication(afc, CFStr(os.path.abspath(path)), None, self._transferCallback, None)
            if e != 0:
                raise RuntimeError('AMDeviceTransferApplication returned %d' % e)
        finally:
            self.stopService(afc)

    def installApplication(self, path):
        afc = self.startService("com.apple.mobile.installation_proxy")
        try:

            items = 1
            keys = (ctypes.c_void_p * items)(CFStr('PackageType'))
            values = (ctypes.c_void_p * items)(CFStr('Developer'))

            options = CFDictionaryCreate(None, keys, values, items, ctypes.byref(kCFTypeDictionaryKeyCallBacks), ctypes.byref(kCFTypeDictionaryValueCallBacks))

            e = AMDeviceInstallApplication(afc, CFStr(path), options, self._installCallback, None)
            if e != 0:
                raise RuntimeError('AMDeviceInstallApplication returned %d' % e)
        finally:
            self.stopService(afc)

    def uninstallApplication(self, bundleId):
        afc = self.startService("com.apple.mobile.installation_proxy")
        try:
            e = AMDeviceUninstallApplication(afc, CFStr(bundleId), None, self._uninstallCallback, None)
            if e != 0:
                raise RuntimeError('AMDeviceUninstallApplication returned %d' % e)
        finally:
            self.stopService(afc)

        items = 1

    def lookupApplications(self):
        self.connect()
        try:
            self.startSession()
            try:
                dictionary = CFDictionaryRef()
                e = AMDeviceLookupApplications(self._device, 0, ctypes.byref(dictionary))
                if e != 0:
                    raise RuntimeError('AMDeviceLookupApplications returned %d' % e)
                return CFDictionaryToDict(dictionary)
            finally:
                self.stopSession()
        finally:
            self.disconnect()

    def lookupApplicationExecutable(self, identifier):
        dictionary = self.lookupApplications()
        try:
            return '%s/%s' % (dictionary[identifier]['Path'], dictionary[identifier]['CFBundleExecutable'])
        except KeyError:
            raise RuntimeError('%s not found in app list.' % identifier)

    def stopService(self, fd):
        if sys.platform == 'win32':
            ws2_32.closesocket(fd)
        else:
            os.close(fd)

    def showStatus(self, action, dictionary):
        show = ['[%s]' % action]

        percentComplete = CFDictionaryGetValue(dictionary, CFStr('PercentComplete'))
        if percentComplete:
            percent = ctypes.c_int()
            CFNumberGetValue(percentComplete, kCFNumberSInt32Type, ctypes.byref(percent))
            show.append(str.rjust('%d%%' % percent.value, 4))

        show.append(CFStringGetStr(CFDictionaryGetValue(dictionary, CFStr('Status'))))

        path = CFDictionaryGetValue(dictionary, CFStr('Path'))
        if path:
            show.append(CFStringGetStr(path))

        print ' '.join(show)

    def debugServer(self):
        service = self.startService('com.apple.debugserver')
        if sys.platform == 'win32':
            return MockSocket(service)
        else:
            return socket.fromfd(service, socket.AF_INET, socket.SOCK_STREAM)

    def _timer(self, timer, info):
        CFRunLoopStop(CFRunLoopGetCurrent())

    def _transfer(self, dictionary, user):
        self.showStatus('Transferring', dictionary)
        return 0

    def _install(self, dictionary, user):
        self.showStatus('Installing', dictionary)
        return 0

    def _uninstall(self, dictionary, user):
        self.showStatus('Uninstalling', dictionary)
        return 0

    def _mount(self, dictionary, user):
        self.showStatus('Mounting', dictionary)
        return 0

    def _deviceNotification(self, info, user):
        info = info.contents
        if info.msg == ADNCI_MSG_CONNECTED:
            if self._waitForDeviceId is None or self._waitForDeviceId == CFStringGetStr(AMDeviceCopyDeviceIdentifier(ctypes.c_void_p(info.dev))):
                self._device = ctypes.c_void_p(info.dev)
                CFRunLoopStop(CFRunLoopGetCurrent())
        elif info.msg == ADNCI_MSG_DISCONNECTED:
            self._device = None
        elif info.msg == ADNCI_MSG_UNKNOWN:
            # This happens as we're closing.
            pass
        else:
            raise RuntimeError('Unexpected device notification status: %d' % info.msg)

class AFCFile(object):
    def __init__(self, afc, path, mode):
        self._afc = afc
        self._mode = ctypes.c_ulonglong(0)
        # http://www.hydrogenaud.io/forums/index.php?showtopic=45160&st=890
        # mode 1 = read
        # mode 2 = read + write
        # mode 3 = write new
        # mode 4 = write new + read
        # mode 5 = write
        # mode 6 = read + write
        # MobileDevice.h: mode 2 = read, mode 3 = write 
        if 'r' in mode:
            self._mode.value |= 1
        if 'w' in mode:
            self._mode.value |= 3
        self._file = AFCFileRef()
        self._open = False

        result = AFCFileRefOpen(self._afc, path.encode('utf-8'), self._mode, ctypes.byref(self._file))
        if result != 0:
            raise RuntimeError('AFCFileRefOpen returned %d' % result)
        if not self._file:
            raise RuntimeError('AFCFileRefOpen did not open a file')
        self._open = True

    def close(self):
        if self._open:
            result = AFCFileRefClose(self._afc, self._file)
            if result != 0:
                raise RuntimeError('AFCFileRefClose returned %d' % result)
            self._open = False

    def read(self, length):
        readLength = ctypes.c_uint32(length)
        data = (ctypes.c_char * length)()
        result = AFCFileRefRead(self._afc, self._file, data, ctypes.byref(readLength))
        if result != 0:
            raise RuntimeError('AFCFileRefRead returned %d' % result)
        return data.raw[:readLength.value]

    def write(self, data):
        length = ctypes.c_uint(len(data))
        pointer = ctypes.c_char_p(data)
        result = AFCFileRefWrite(self._afc, self._file, pointer, length)
        if result != 0:
            raise RuntimeError('AFCFileRefWrite returned %d' % result)

class AFC(object):
    '''
    Error codes
         7 Bad arguments
         8 Permission denied (no read access), or file not found
        10 Permission denied (no write access)
    (from fruitstrap::MobileDevice.h)
         1 syscall
         3 out of mmory
         4 query failed
        11 invalid argument
        37 dict not loaded (0x25)
        22 arg null
        See also
        https://www.theiphonewiki.com/wiki/MobileDevice_Library#Known_Error_Codes
    '''

    def __init__(self, session):
        self._session = session
        self._afc = AFCConnectionRef()
        result = AFCConnectionOpen(self._session, 0, ctypes.byref(self._afc))
        if result != 0:
            raise RuntimeError('AFCConnectionOpen returned %d' % result)

    def open(self, path, mode):
        return AFCFile(self._afc, path, mode)

    def close(self):
        AFCConnectionClose(self._afc)

    # Top level directory seems write protected, so create under
    # Documents/ or tmp/
    def mkdir(self, path):
        result = AFCDirectoryCreate(self._afc, path)
        if result != 0:
            raise RuntimeError('AFCDirectoryCreate returned %d' % result)

    def remove_path(self, path):
        result = AFCRemovePath(self._afc, path)
        if result != 0:
            raise RuntimeError('AFCRemovePath %s returned %d' % (path, result))

    def listdir(self, path):
        directory = AFCDirectoryRef()
        result = AFCDirectoryOpen(self._afc, path.encode('utf-8'), ctypes.byref(directory))
        if result != 0:
            raise OSError('AFCDirectoryOpen returned %d' % result)
        name = ctypes.c_char_p()
        entries = []
        while AFCDirectoryRead(self._afc, directory, ctypes.byref(name)) == 0:
            if name.value is None:
                break
            path = name.value.decode('utf-8')
            if not path in ('.', '..'):
                entries.append(path)
        AFCDirectoryClose(self._afc, directory)
        return entries

class DeviceSupportPaths(object):
    """
    A small helper for finding various Xcode directories.

    Written from fruitstrap.c, trial and error, and lldb's
    PlatformRemoteiOS.cpp:
    <https://llvm.org/viewvc/llvm-project/lldb/trunk/source/Plugins/Platform/MacOSX/PlatformRemoteiOS.cpp?view=markup>
    """
    def __init__(self, target, productVersion, buildVersion):
        self._target = target
        self._productVersion = productVersion
        self._buildVersion = buildVersion

        self._deviceSupportDirectory = None
        self._deviceSupportForOsVersion = None
        self._developerDiskImagePath = None

    def deviceSupportDirectory(self):
        if not self._deviceSupportDirectory:
            self._deviceSupportDirectory = subprocess.check_output(['xcode-select', '-print-path']).strip()
        return self._deviceSupportDirectory

    def deviceSupportDirectoryForOsVersion(self):
        if not self._deviceSupportForOsVersion:
            path = os.path.join(self.deviceSupportDirectory(), 'Platforms', self._target + '.platform', 'DeviceSupport')

            attempts = [os.path.join(path, attempt) for attempt in self.versionPermutations()]

            for attempt in attempts:
                if os.path.exists(attempt):
                    self._deviceSupportForOsVersion = attempt
                    break
            if not self._deviceSupportForOsVersion:
                raise RuntimeError('Could not find device support directory for %s %s (%s).' % (self._target, self._productVersion, self._buildVersion))
        return self._deviceSupportForOsVersion

    def versionPermutations(self):
            shortProductVersion = '.'.join(self._productVersion.split('.')[:2])
            return [
                '%s (%s)' % (self._productVersion, self._buildVersion),
                '%s (%s)' % (shortProductVersion, self._buildVersion),
                '%s' % self._productVersion,
                '%s' % shortProductVersion,
                'Latest',
            ]

    def developerDiskImagePath(self):
        if not self._developerDiskImagePath:
            path = os.path.join(self.deviceSupportDirectory(), 'Platforms', self._target + '.platform', 'DeviceSupport')
            attempts = [os.path.join(path, attempt, 'DeveloperDiskImage.dmg') for attempt in self.versionPermutations()]
            for attempt in attempts:
                if os.path.exists(attempt):
                    self._developerDiskImagePath = attempt
                    break
            if not self._developerDiskImagePath:
                raise RuntimeError('Could not find developer disk image for %s %s (%s).' % (self._target, self._productVersion, self._buildVersion))
        return self._developerDiskImagePath

class DebuggerException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class GdbServer(object):
    """
    Given a socket connected to a remote debugserver, this speaks just enough
    of the GDB Remote Serial Protocol
    <http://sourceware.org/gdb/onlinedocs/gdb/Remote-Protocol.html> to launch
    an application and display its output.

    Usage:
        GdbServer(connectedSocket).run('/path/to/executable', 'arg1', 'arg2')
    """
    def __init__(self, connectedSocket):
        self._socket = connectedSocket
        self.exitCode = None
        self._readBuffer = ''

    def read(self):
        startIndex = self._readBuffer.find('$')
        endIndex = self._readBuffer.find('#', startIndex)
        while startIndex == -1 or endIndex == -1 or len(self._readBuffer) < endIndex + 3:
            data = self._socket.recv(4096)
            if not data:
                break
            self._readBuffer += data
            startIndex = self._readBuffer.find('$')
            endIndex = self._readBuffer.find('#', startIndex)

        # Discard any ACKs.  We trust we're on a reliable connection.
        while self._readBuffer.startswith('+'):
            self._readBuffer = self._readBuffer[1:]

        payload = None
        startIndex = self._readBuffer.find('$')
        endIndex = self._readBuffer.find('#', startIndex)
        if startIndex != -1 and endIndex != -1 and len(self._readBuffer) >= endIndex + 3:
            payload = self._readBuffer[startIndex + 1:endIndex]
            checksum = self._readBuffer[endIndex + 1:endIndex + 3]
            if checksum != '00':
                calculated = '%02x' % (sum(ord(c) for c in payload) & 255)
                if checksum != calculated:
                    raise RuntimeError('Bad response checksum (%s vs %s).' % (checksum, calculated))

        self._readBuffer = self._readBuffer[endIndex + 3:]

        return payload

    def send(self, packet):
        data = '$%s#%02x' % (packet, sum(ord(c) for c in packet) & 255)
        self._socket.sendall(data)
        stopReply = [True for command in ['C', 'c', 'S', 's', 'vCont', 'vAttach', 'vRun', 'vStopped', '?'] if packet.startswith(command)]

        if stopReply:
            resume = True
            while resume:
                resume = False
                response = self.read()
                if response:
                    if response.startswith('S'):
                        signal = '0x' + response[1:3]
                        message = 'Program received signal %s. (registers unavailable)' % signal
                        raise DebuggerException(message)
                    elif response.startswith('T'):
                        signal = '0x' + response[1:3]
                        message = 'Program received signal %s.' % signal
                        for pair in response[4:].split(';'):
                            message += '\n%s' % pair
                        raise DebuggerException(message)
                    elif response.startswith('W'):
                        self.exitCode = int(response[1:], 16)
                        if self.exitCode != 0 :
                            print 'Process returned %d.' % self.exitCode
                    elif response.startswith('X'):
                        signal = '0x' + response[1:3]
                        if ';' in response:
                            response = response.split(';', 1)[1]
                        raise DebuggerException('Process terminated with signal %s (%s).' % (signal, response))
                    elif response.startswith('O'):
                        print response[1:].decode('hex'),
                        resume = True
                    elif response.startswith('F'):
                        raise RuntimeError('GDB File-I/O Remote Protocol Unimplemented.')
                    else:
                        raise RuntimeError('Unexpected response to stop reply packet: ' + response)
        else:
            response = self.read()
        return response

    def run(self, *argv):
        self.send('QStartNoAckMode')
        self._socket.sendall('+')
        self.send('QEnvironmentHexEncoded:')
        self.send('QSetDisableASLR:1')
        self.send('A' + ','.join('%d,%d,%s' % (len(arg) * 2, i, arg.encode('hex')) for i, arg in enumerate(argv)))
        self.send('qLaunchSuccess')
        self.send('vCont;c')

    def kill(self):
        self.send('k')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage and launch applications on iOS.')

    group = parser.add_argument_group('Global Configuration')
    group.add_argument('-b', '--bundle', help='path to local app bundle to operate on')
    group.add_argument('-id', '--appid', help='application identifier to operate on')
    group.add_argument('-t', '--timeout', type=float, help='seconds to wait for slow operations before giving up')
    group.add_argument('-dev', '--device-id', help='device id of specific device to communicate with')

    group = parser.add_argument_group('Application Management')
    group.add_argument('-i', '--install', action='store_true', help='install an application')
    group.add_argument('-u', '--uninstall', action='store_true', help='uninstall an application')
    group.add_argument('-l', '--list-applications', action='store_true', help='list installed applications')

    group.add_argument('-r', '--run', action='store_true', help='run an application')
    group.add_argument('-a', '--arguments', nargs=argparse.REMAINDER, help='arguments to pass to application being run')

    group = parser.add_argument_group('Developer Disk Image')
    group.add_argument('-m', '--mount', action='store_true', help='mount developer disk image (must be done at least once to run)')
    group.add_argument('-ddi', '--developer-disk-image', type=str, help='path to DeveloperDiskImage.dmg')

    group = parser.add_argument_group('File Access')
    group.add_argument('-get', '--get-file', nargs=2, metavar=('DEVICE_FILE', 'LOCAL_FILE'), help='read a file from the device')
    group.add_argument('-put', '--put-file', nargs=2, metavar=('LOCAL_FILE', 'DEVICE_FILE'), help='write a file to the device')
    group.add_argument('-ls', '--list-files', nargs='?', metavar='PATH', const='.', help='recursively list all files and directories, starting at the root or given path')

    arguments = parser.parse_args()

    if not arguments.install \
        and not arguments.uninstall \
        and not arguments.run \
        and not arguments.list_applications \
        and not arguments.mount \
        and not arguments.get_file \
        and not arguments.put_file \
        and not arguments.list_files:
        print 'Nothing to do.'
        sys.exit(0)

    mdm = MobileDeviceManager()
    if arguments.device_id:
        print 'Waiting for a device with UDID %s...' % arguments.device_id
    else:
        print 'Waiting for a device...'
    if not mdm.waitForDevice(timeout=arguments.timeout, device=arguments.device_id):
        print 'Gave up waiting for a device.'
        sys.exit(1)

    print 'Connected to device with UDID:', mdm.deviceId()

    if arguments.uninstall:
        bundle = arguments.appid or mdm.bundleId(arguments.bundle)
        print '\nUninstalling %s...' % bundle
        mdm.uninstallApplication(bundle)

    if arguments.install:
        print '\nInstalling %s...' % arguments.bundle
        mdm.transferApplication(arguments.bundle)
        mdm.installApplication(arguments.bundle)

    if arguments.list_applications:
        print '\nInstalled applications:'
        applications = mdm.lookupApplications()
        bundleIdentifiers = applications.keys()
        bundleIdentifiers.sort()
        for bundleId in bundleIdentifiers:
            print bundleId

    if arguments.mount:
        if arguments.developer_disk_image:
            ddi = arguments.developer_disk_image
        else:
            ddi = DeviceSupportPaths('iPhoneOS', mdm.productVersion(), mdm.buildVersion()).developerDiskImagePath()
        print '\nMounting %s...' % ddi
        mdm.mountImage(ddi)

    if arguments.run:
        executable = mdm.lookupApplicationExecutable(arguments.appid or mdm.bundleId(arguments.bundle))
        db = mdm.debugServer()
        if arguments.timeout > 0:
            db.settimeout(arguments.timeout)
        debugger = GdbServer(db)
        argv = [executable]
        if arguments.arguments:
            argv += arguments.arguments
        print '\nRunning %s...' % ' '.join(argv)
        try:
            debugger.run(*argv)
        except DebuggerException, e:
            print e
            sys.exit(1)
        sys.exit(debugger.exitCode)

    if arguments.get_file or arguments.put_file or arguments.list_files:
        if arguments.appid or arguments.bundle:
            afc = AFC(mdm.startHouseArrestService(arguments.appid or mdm.bundleId(arguments.bundle)))
        else:
            afc = AFC(mdm.startService('com.apple.afc'))

        if arguments.get_file:
            readFile = afc.open(arguments.get_file[0], 'r')
            writeFile = open(arguments.get_file[1], 'wb')
            size = 0
            while True:
                data = readFile.read(8192)
                if not data:
                    break
                writeFile.write(data)
                size += len(data)
            writeFile.close()
            readFile.close()
            print '%d bytes read from %s.' % (size, arguments.get_file[0])
        elif arguments.put_file:
            readFile = open(arguments.put_file[0], 'rb')
            writeFile = afc.open(arguments.put_file[1], 'w')
            size = 0
            while True:
                data = readFile.read(8192)
                if not data:
                    break
                writeFile.write(data)
                size += len(data)
            writeFile.close()
            readFile.close()
            print '%d bytes written to %s.' % (size, arguments.put_file[1])
        elif arguments.list_files:
            print 'Listing %s:' % arguments.list_files
            def walk(root, indent=0):
                print '  ' * indent + root
                try:
                    children = afc.listdir(root)
                except:
                    children = []
                for child in children:
                    walk(root.rstrip('/') + '/' + child, indent + 1)
            walk(arguments.list_files)
        afc.close()

    mdm.close()

