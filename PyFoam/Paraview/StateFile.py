"""
Represents a Paraview State-fime (pvsm) and manipulates it
"""

from xml.dom.minidom import parse
import xml.dom
from os import path
import os
import shutil
import glob

from PyFoam.Error import error
from PyFoam import configuration as config
from tempfile import mkstemp

class StateFile(object):
    """The actual PVSM-file

    Stores the actual file as an xml-file"""
    def __init__(self,fName):
        """@param fName: the XML-file that represents the Paraview-state"""

        dom=parse(fName)
        self.doc=dom.documentElement

    def readerType(self):
        """Returns the type of the used OF-Reader as a string"""
        return self.getReader().data.getAttribute("type")

    def setCase(self,case):
        """Rewrite the state-file so that it uses another case than the one
        predefined in the state-file
        @param case: The path to the new case-file"""
        reader=self.getReader()
        typ=reader.data.getAttribute("type")
        if typ=="PV3FoamReader":
            reader.setProperty("FileName",case)
        elif typ=="OpenFOAMReader":
            oldFile=reader.getProperty("FileName")
            fName=path.basename(oldFile)
            newFile=path.join(path.dirname(case),fName)
            if not path.exists(newFile):
                open(newFile,"w")
            reader.setProperty("FileName",newFile)
        else:
            error("Reader type",typ,"not implemented for state-file rewritting")

    def setDecomposed(self,isDecomposed):
        """Sets whether the decomposed or the reconstructed data should be used
        in the state-file. If this can not be set a string with the error message
        is returned"""
        reader=self.getReader()
        typ=reader.data.getAttribute("type")
        if typ=="PV3FoamReader":
            return "File type "+typ+" does not support parallel reading"
        elif typ=="OpenFOAMReader":
            oldDeco=int(reader.getProperty("CaseType"))
            if isDecomposed:
                newDeco=0
            else:
                newDeco=1
            if newDeco==oldDeco:
                return "Decomposed/Reconstruced correctly set. Nothing changed"
            reader.setProperty("CaseType",str(newDeco))
        else:
            error("Reader type",typ,"not implemented for state-file rewritting")

    def __str__(self):
        """Write the file as a string"""
        return self.doc.toxml()

    def writeTemp(self):
        """Write the state to a temporary file and return the name of that file"""
        fd,fn=mkstemp(suffix=".pvsm",text=True)

        fh=os.fdopen(fd,"w")
        fh.write(str(self))
        fh.close()

        return fn

    def serverState(self):
        tmp=self.doc.getElementsByTagName("ServerManagerState")
        if len(tmp)!=1:
            error("Wrong number of ServerManagerStates:",len(tmp))

        return tmp[0]

    def getProxy(self,type_):
        """Return a list of Prxy-elements that fit a specific type"""
        result=[]

        for p in self.serverState().getElementsByTagName("Proxy"):
            tp=p.getAttribute("type")
            if type_==tp:
                result.append(Proxy(p))

        return result

    def getReader(self):
        """Return the Proxy-Element with the reader"""
        tmp=self.getProxy("PV3FoamReader")+self.getProxy("OpenFOAMReader")
        if len(tmp)!=1:
            error("Wrong number of Readers in State-File. Need 1 but got",len(tmp))

        return tmp[0]

    def rewriteTexts(self,values):
        """Rewrite all Text-Objects so that strings of the form %%(key)s get replaced
        @param values: dictionary with the values"""
        tmp=self.getProxy("TextSource")
        for t in tmp:
            t.rewriteProperty("Text",values)

class Proxy(object):
    """Convenience class for handling proxies"""
    def __init__(self,xml):
        self.data=xml

    def setProperty(self,name,value,index=None):
        """Set a property in a proxy

        @param name: name of the property
        @param value: the new value
        @param index: Index. If not specified all elements are changed"""

        for p in self.data.getElementsByTagName("Property"):
            if p.getAttribute("name")==name:
                for e in p.getElementsByTagName("Element"):
                    if index==None or index==int(e.getAttribute("index")):
                        e.setAttribute("value",str(value))

    def getProperty(self,name,index=None):
        """Get a property in a proxy

        @param name: name of the property
        @param index: Index. If not specified all elements are changed"""

        for p in self.data.getElementsByTagName("Property"):
            if p.getAttribute("name")==name:
                for e in p.getElementsByTagName("Element"):
                    if index==None or index==int(e.getAttribute("index")):
                        return e.getAttribute("value")
        return None

    def rewriteProperty(self,name,values,index=None):
        """Rewrites a property by replacing all strings of the form %%(key)s
        (Python-notation for dictionary-replacement) with a corresponding value

        @param name: name of the property
        @param values: Dictionary with the keys and the corresponding values
        @param index: Index. If not specified all elements are changed"""

        for p in self.data.getElementsByTagName("Property"):
            if p.getAttribute("name")==name:
                for e in p.getElementsByTagName("Element"):
                    if index==None or index==int(e.getAttribute("index")):
                        old = e.getAttribute("value")
                        new = old % values
                        if new!=old:
                            # print "Replacing",old,"with",new
                            e.setAttribute("value",new)
