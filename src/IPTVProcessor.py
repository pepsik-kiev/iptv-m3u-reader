from enigma import eServiceReference, eDVBDB
from ServiceReference import ServiceReference
from Components.config import config
from time import time
from twisted.internet import threads
import twisted.python.runtime
import socket
import urllib
import re

idIPTV = 0x13E9
db = eDVBDB.getInstance()

class IPTVProcessor():
	def __init__(self):
		self.last_exec = None
		self.playlist = None
		self.isPlayBackup = False
		self.iptv_service_provider = ""
		self.url = ""
		self.offset = 0
		self.refresh_interval = 1
		self.scheme = ""
		self.search_criteria = "tvg-id=\"{SID}\""
		self.play_system = "4097"
		self.static_urls = False
		self.ignore_vod = True
		
	def getPlaylistAndGenBouquet(self, callback=None):
		if callback:
			threads.deferToThread(self.storePlaylistAndGenBouquet).addCallback(callback)
		else:
			self.storePlaylistAndGenBouquet()
		
	def storePlaylistAndGenBouquet(self):
		is_check_network_val = config.plugins.m3uiptv.check_internet.value
		if is_check_network_val != "off":
			socket.setdefaulttimeout(int(is_check_network_val))
			socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
		req = urllib.request.Request(self.url, headers={'User-Agent' : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"}) 
		req_timeout_val = config.plugins.m3uiptv.req_timeout.value
		if req_timeout_val != "off":
			response = urllib.request.urlopen(req, timeout=int(req_timeout_val))
		else:
			response = urllib.request.urlopen(req)
		playlist = response.read().decode('utf-8')
		self.playlist = playlist
		playlist_splitted = playlist.splitlines()
		tsid = 1000
		services = []
		line_nr = 0
		for line in playlist_splitted:
			if self.ignore_vod and "group-title=\"VOD" in line:
				continue
			if line.startswith("#EXTINF:"):
				condition = re.escape(self.search_criteria).replace("\\{SID\\}", "(.*?)") + r".*,(.*)"
				match = re.search(condition, line)
				isFallbackMatch = False
				if not match:
					# Probably the format of the playlist is not m3u+ or for some reason it doesnt contain
					# tvg-id, tvg-name and other similar tags. In this case try matching by the name of service
					condition = r".*,(.*)"
					match = re.search(condition, line)
					isFallbackMatch = True
				if match:
					sid = match.group(1).replace(":", "%3a")
					ch_name = match.group(2) if not isFallbackMatch else sid
					if not sid:
						sid = ch_name.replace(":", "%3a")
					url = ""
					if self.static_urls:
						found_url = False
						next_line_nr = line_nr + 1
						while not found_url:
							if len(playlist_splitted) > next_line_nr:
								next_line = playlist_splitted[next_line_nr].strip()
								if next_line.startswith(("http://", "https://")):
									url = next_line.replace(":", "%3a")
									found_url = True
							else:
								break
					else:
						url = self.scheme + "%3a//" + sid
					stype = "1"
					if "UHD" in ch_name or "4K" in ch_name:
						stype = "1F"
					elif "HD" in ch_name:
						stype = "19"
					sref = "%s:0:%s:%d:%d:1:CCCC0000:0:0:0:%s:%s•%s" % (self.play_system, stype, tsid, self.onid, url, ch_name, self.iptv_service_provider)
					tsid += 1
					services.append(sref)
			line_nr += 1
		db.addOrUpdateBouquet(self.iptv_service_provider, services, 1)

	def processService(self, nref, iptvinfodata, callback=None):
		splittedRef = nref.toString().split(":")
		sRef = nref and ServiceReference(nref.toString())
		origRef = ":".join(splittedRef[:10])
		iptvInfoDataSplit = iptvinfodata[0].split("|*|")
		channelForSearch = iptvInfoDataSplit[0].split(":")[0]
		#catchUpDays = 0
		#if len(iptvInfoDataSplit) > 1:
		#	catchUpDays = int(iptvInfoDataSplit[1])
		#print "[IPTV] channelForSearch = " + channelForSearch
		#print "[IPTV] orig_name = " + orig_name
		orig_name = sRef and sRef.getServiceName()
		backup_ref = nref.toString()
		try:
			backup_ref = iptvinfodata[1].split(":")[0].replace("%3a", ":")
		except:
			pass
		if callback:
			threads.deferToThread(self.processDownloadPlaylist, nref, channelForSearch, origRef, backup_ref, orig_name).addCallback(callback)
		else:
			return self.processDownloadPlaylist(nref, channelForSearch, origRef, backup_ref, orig_name) , nref, False
		return nref, nref, True
		
	def processDownloadPlaylist(self, nref, channelForSearch, origRef, backup_ref, orig_name):
		try:
			is_check_network_val = config.plugins.m3uiptv.check_internet.value
			if is_check_network_val != "off":
				socket.setdefaulttimeout(int(is_check_network_val))
				socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
			channelForSearch = channelForSearch.replace("%3a", ":")
			channelSID = self.search_criteria.replace("{SID}", channelForSearch)
			prov = self
			cache_time = 0
			if prov.refresh_interval > -1:
				cache_time = int(prov.refresh_interval * 60 * 60)
			nref_new = nref.toString()
			cur_time = time()
			time_delta = prov.last_exec and cur_time - prov.last_exec or None
			if (prov.refresh_interval == -1 and prov.playlist) or (prov.refresh_interval > 0 and time_delta and  time_delta < cache_time):
				playlist = prov.playlist
			else:
				req = urllib.request.Request(prov.url, headers={'User-Agent' : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"}) 
				req_timeout_val = config.plugins.m3uiptv.req_timeout.value
				if req_timeout_val != "off":
					response = urllib.request.urlopen(req, timeout=int(req_timeout_val))
				else:
					response = urllib.request.urlopen(req)
				playlist = response.read().decode('utf-8')
				prov.playlist = playlist
				if cache_time > 0:
					prov.last_exec = cur_time

			findurl = False
			for line in playlist.splitlines():
				line = line.strip()  # just in case there is surrounding white space present
				if line.startswith("#EXTINF:"):
					findurl = (channelSID in line) or (("," + channelForSearch) in line)
				elif findurl and line.startswith(("http://", "https://")):
					iptv_url = line.replace(":", "%3a")
					nref_new = origRef + ":" + iptv_url + ":" + orig_name + "•" + prov.iptv_service_provider
					break
			self.nnref = eServiceReference(nref_new)
			self.isPlayBackup = False
			return self.nnref#, nref
		except Exception as ex:
			print("EXCEPTION: " + str(ex))
			self.isPlayBackup = True
			self.nnref = eServiceReference(backup_ref + ":")
			return self.nnref#, nref