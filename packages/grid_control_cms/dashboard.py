#-#  Copyright 2009-2016 Karlsruhe Institute of Technology
#-#
#-#  Licensed under the Apache License, Version 2.0 (the "License");
#-#  you may not use this file except in compliance with the License.
#-#  You may obtain a copy of the License at
#-#
#-#      http://www.apache.org/licenses/LICENSE-2.0
#-#
#-#  Unless required by applicable law or agreed to in writing, software
#-#  distributed under the License is distributed on an "AS IS" BASIS,
#-#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#-#  See the License for the specific language governing permissions and
#-#  limitations under the License.

import os, time
from grid_control.job_db import Job
from grid_control.monitoring import Monitoring
from grid_control.utils.thread_tools import start_thread
from grid_control_cms.DashboardAPI import DashboardAPI

class DashBoard(Monitoring):
	configSections = Monitoring.configSections + ['dashboard']

	def __init__(self, config, name, task):
		Monitoring.__init__(self, config, name, task)
		jobDesc = task.getDescription(None) # TODO: use the other variables for monitoring
		self.app = config.get('application', 'shellscript', onChange = None)
		jobType = utils.QM(jobDesc.jobType, jobDesc.jobType, 'analysis')
		self.tasktype = config.get('task', jobType, onChange = None)
		self.taskname = config.get('task name', '@GC_TASK_ID@_@DATASETNICK@', onChange = None)
		self._statusMap = {Job.DONE: 'DONE', Job.FAILED: 'DONE', Job.SUCCESS: 'DONE',
			Job.RUNNING: 'RUNNING', Job.ABORTED: 'ABORTED', Job.CANCELLED: 'CANCELLED'}


	def getScript(self):
		yield utils.pathShare('mon.dashboard.sh', pkg = 'grid_control_cms')


	def getTaskConfig(self):
		return { 'TASK_NAME': self.taskname, 'DB_EXEC': self.app, 'DATASETNICK': '' }


	def getFiles(self):
		for fn in ('DashboardAPI.py', 'Logger.py', 'ProcInfo.py', 'apmon.py', 'report.py'):
			yield utils.pathShare('..', 'DashboardAPI', fn, pkg = 'grid_control_cms')


	def publish(self, jobObj, jobNum, taskId, usermsg):
		(header, backend, rawId) = jobObj.wmsId.split('.', 2)
		dashId = '%s_%s' % (jobNum, rawId)
		if "http" not in jobObj.wmsId:
			dashId = '%s_https://%s:/%s' % (jobNum, backend, rawId)
		msg = utils.mergeDicts([{'taskId': taskId, 'jobId': dashId, 'sid': rawId}] + usermsg)
		DashboardAPI(taskId, dashId).publish(**utils.filterDict(msg, vF = lambda v: v is not None))


	# Called on job submission
	def onJobSubmit(self, wms, jobObj, jobNum):
		token = wms.getAccessToken(jobObj.wmsId)
		taskId = self.task.substVars(self.taskname, jobNum, addDict = {'DATASETNICK': ''}).strip('_')
		start_thread("Notifying dashboard about job submission %d" % jobNum,
			self.publish, jobObj, jobNum, taskId, [{
			'user': os.environ['LOGNAME'], 'GridName': '/CN=%s' % token.getUsername(), 'CMSUser': token.getUsername(),
			'tool': 'grid-control', 'JSToolVersion': utils.getVersion(),
			'SubmissionType':'direct', 'tool_ui': os.environ.get('HOSTNAME', ''),
			'application': self.app, 'exe': 'shellscript', 'taskType': self.tasktype,
			'scheduler': wms.wmsName, 'vo': token.getGroup()}, self.task.getSubmitInfo(jobNum)])


	# Called on job status update
	def onJobUpdate(self, wms, jobObj, jobNum, data, addMsg = {}):
		# Translate status into dashboard status message
		statusDashboard = self._statusMap.get(jobObj.state, 'PENDING')
		# Update dashboard information
		taskId = self.task.substVars(self.taskname, jobNum, addDict = {'DATASETNICK': ''}).strip('_')
		start_thread("Notifying dashboard about status of job %d" % jobNum,
			self.publish, jobObj, jobNum, taskId, [{'StatusValue': statusDashboard,
			'StatusValueReason': data.get('reason', statusDashboard).upper(),
			'StatusEnterTime': data.get('timestamp', time.strftime('%Y-%m-%d_%H:%M:%S', time.localtime())),
			'StatusDestination': data.get('dest', '') }, addMsg])


	def onJobOutput(self, wms, jobObj, jobNum, retCode):
		self.onJobUpdate(wms, jobObj, jobNum, jobObj, {'ExeExitCode': retCode})


	def onTaskFinish(self, nJobs):
		utils.wait(5)
