import os
from xml.sax.saxutils import escape

from enigma import eEPGCache

try:
	import Plugins.Extensions.EPGImport.EPGConfig as EPGConfig
	import Plugins.Extensions.EPGImport.EPGImport as EPGImport
except ImportError:  # plugin not available
	EPGImport = None
	EPGConfig = None


EPGIMPORTPATH = '/etc/epgimport/'

class epgimport_helper():
	def __init__(self, provider):
		self.provider = provider

	@staticmethod
	def xml_escape(string):
		return escape(string, {'"': '&quot;', "'": "&apos;"})
	
	def getSourcesFilename(self):
		return os.path.join(EPGIMPORTPATH, 'm3uiptv.%s.sources.xml' % self.provider.scheme)
	
	def getChannelsFilename(self):
		return os.path.join(EPGIMPORTPATH, 'm3uiptv.%s.channels.xml' % self.provider.scheme)
	
	def createSourcesFile(self):
		sources_out = [
			'<sources>',
			' <sourcecat sourcecatname="M3UIPTV plugin">',
			'  <source type="gen_xmltv" nocheck="1" channels="%s">' % self.getChannelsFilename(),
			'   <description>%s</description>' % self.xml_escape(self.provider.iptv_service_provider),
			'   <url><![CDATA[%s]]></url>' % self.provider.getEpgUrl(),
			'  </source>',
			' </sourcecat>',
			'</sources>']
		with open(os.path.join(self.getSourcesFilename()), "w") as f:
			f.write("\n".join(sources_out))

	def createChannelsFile(self, groups):
		channels_out = ['<channels>']
		for group in groups:
			channels_out.append(f' <!-- {groups[group][0]} -->')
			for service in groups[group][1]:
				sref, epg_id, ch_name = service
				channels_out.append(f' <channel id="{epg_id}>{self.provider.generateEPGChannelReference(sref)}</channel> <!-- {ch_name} -->')
		channels_out.append('</channels>')
		with open(os.path.join(self.getChannelsFilename()), "w") as f:
			f.write("\n".join(channels_out))

	#  not working yet
	def importepg(self):
		if EPGImport and EPGConfig and os.path.exists(f := self.getSourcesFilename()):
			epgimport = EPGImport.EPGImport(eEPGCache.getInstance(), lambda x: True)
			epgimport.sources = [EPGConfig.enumSourcesFile(f)]
			epgimport.onDone = self.epgimport_done
			epgimport.beginImport()

	def epgimport_done(self, reboot=False, epgfile=None):
		print('epgimport of "%s" finished' % self.provider.iptv_service_provider)
		