#
# Revision: 1.3 $"
# Id: DBSXMLParser.java,v 1.3 2006/10/26 18:26:04 afaq Exp $"
#
import os, re, string, gzip
from dbsException import DbsException
from dbsApiException import *
from dbsExecHandler import DbsExecHandler


import os, re, string, xml.sax, xml.sax.handler
from xml.sax.saxutils import escape


class DbsExecService:

  """Provides Server connectivity through HTTP"""
  def __init__(self, Home, JavaHome,  ApiVersion, Args={}):
    """ Constructor. """
    
    self.Home = Home
    self.JavaHome = JavaHome
    self.ApiVersion = ApiVersion
    
  def _call (self, args, type):
    """
    The local execution is similar except we pass call details via
    environment variables and form data on standard input to the shell
    script.  The output isn't compressed.  (FIXME: Not implemented!)
    """

    try:
       #import pdb
       #pdb.set_trace()
       classpath=""
       classpathbase= self.Home+'/lib/' 
       for ajar in os.listdir(classpathbase):
           if ajar.endswith('.jar'):
              classpath+=classpathbase+ajar+':'
       request_string = self.JavaHome+'/bin/java -classpath '+classpath+ ' -DDBS_SERVER_CONFIG='+self.Home+'/etc/context.xml dbs.test.DBSCLI'
       

       #request_string = './cli.sh apiversion='+self.ApiVersion

       for key, value in args.items():
                   if (value== ''): continue    
		   request_string += ' "' + key + '=' + value + '"'
           
       request_string += ' apiversion='+self.ApiVersion
       print request_string  

       
       #obj = os.popen('cd ' + self.Home + '/test;' + request_string)
        
       obj = os.popen(request_string)

       tmp = obj.readline()
       data = tmp
       while(tmp != "") :
	       tmp = obj.readline()
	       data += tmp
       #print data	       
       
       # Error message would arrive in XML, if any
       class Handler (xml.sax.handler.ContentHandler):
        def startElement(self, name, attrs):
          if name == 'exception':
             statusCode = attrs['code']
             exmsg = "DBS Server Raised An Error: %s, %s" \
                                 %(attrs['message'], attrs['detail'])

             if (int(statusCode) < 2000 and  int(statusCode) > 1000 ): 
                raise DbsBadRequest (args=exmsg, code=statusCode)

             if (int(statusCode) < 3000 and  int(statusCode) > 2000 ):
                raise DbsDatabaseError (args=exmsg, code=statusCode) 
             
             if (int(statusCode) < 4000 and  int(statusCode) > 3000 ):
                raise DbsBadXMLData (args=exmsg, code=statusCode)

             else: raise DbsExecutionError (args=exmsg, code=statusCode)
  
      
          if name == 'warning':
             print "Waring Message: " + attrs['message']
             print "Warning Detail: " + attrs['detail']
             print "\n\n\n"
             #raise DbsObjectExists (args=exmsg)
 
       xml.sax.parseString (data, Handler ())

       # All is ok, return the data
       return data
    except DbsException, ex:
      # One of our own errors, re-raise
      raise ex

    except DbsToolError, ex:
      # One of our own errors, re-raise
      raise ex

    except Exception, ex:
      #if ex.get('code', "") == "" :
      #   raise DbsToolError (exception=ex, code='unknown')
      #raise DbsException(exception=ex)
      # URL access failed, raise an exception
      raise DbsToolError (exception=ex, code='unknown')
