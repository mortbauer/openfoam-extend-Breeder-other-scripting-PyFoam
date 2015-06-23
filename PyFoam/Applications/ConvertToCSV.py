"""
Application-class that implements pyFoamConvertToCSV.py
"""
from optparse import OptionGroup

from .PyFoamApplication import PyFoamApplication
from .CommonReadWriteCSV import CommonReadWriteCSV

from PyFoam.Basics.SpreadsheetData import SpreadsheetData

from os import path,listdir
from copy import deepcopy
from glob import glob

class ConvertToCSV(PyFoamApplication,
                   CommonReadWriteCSV):
    def __init__(self,
                 args=None,
                 **kwargs):
        description="""\
Takes a plain file with column-oriented data and converts it to a
csv-file.  If more than one file are specified, they are joined
according to the first column.

Note: the first file determines the resolution of the time-axis
"""
        CommonReadWriteCSV.__init__(self)
        PyFoamApplication.__init__(self,
                                   args=args,
                                   description=description,
                                   usage="%prog <source> ... <dest.csv>",
                                   interspersed=True,
                                   changeVersion=False,
                                   nr=2,
                                   exactNr=False,
                                   **kwargs)

    def addOptions(self):
        CommonReadWriteCSV.addOptions(self)

        how=OptionGroup(self.parser,
                         "How",
                         "How the data should be joined")
        self.parser.add_option_group(how)

        how.add_option("--force",
                       action="store_true",
                       dest="force",
                       default=False,
                       help="Overwrite the destination csv if it already exists")
        how.add_option("--extend-data",
                       action="store_true",
                       dest="extendData",
                       default=False,
                       help="Extend the time range if other files exceed the range of the first file")
        how.add_option("--names-from-filename",
                       action="store_true",
                       dest="namesFromFilename",
                       default=False,
                       help="Read the value names from the file-name (assuming that names are split by _ and the names are in the tail - front is the general filename)")
        how.add_option("--add-times",
                       action="store_true",
                       dest="addTimes",
                       default=False,
                       help="Actually add the times from the second file instead of interpolating")
        how.add_option("--interpolate-new-times",
                       action="store_true",
                       dest="interpolateNewTime",
                       default=False,
                       help="Interpolate data if new times are added")
        how.add_option("--new-data-no-interpolate",
                       action="store_false",
                       dest="newDataInterpolate",
                       default=True,
                       help="Don't interpolate new data fields to the existing times")

        excel=OptionGroup(self.parser,
                          "Excel",
                          "Stuff for excel file output")
        self.parser.add_option_group(excel)

        excel.add_option("--add-sheets",
                         action="store_true",
                         dest="addSheets",
                         default=False,
                         help="Add the input data in unmodified form as additional sheets to the excel file")

    def run(self):
        dest=self.parser.getArgs()[-1]
        if path.exists(dest) and not self.opts.force:
            self.error("CSV-file",dest,"exists already. Use --force to overwrite")
        sources=[]
        for s in self.parser.getArgs()[0:-1]:
            if s.find("/*lastTime*/")>=0:
                front,back=s.split("/*lastTime*/",1)
                for d in glob(front):
                    lastTime=None
                    for f in listdir(d):
                        if path.exists(path.join(d,f,back)):
                            try:
                                t=float(f)
                                if lastTime:
                                    if t>float(lastTime):
                                        lastTime=f
                                else:
                                    lastTime=f
                            except ValueError:
                                pass
                    if lastTime:
                        sources.append(path.join(d,lastTime,back))
            else:
                sources.append(s)

        diffs=[None]
        if len(sources)>1:
            # find differing parts
            commonStart=1e4
            commonEnd=1e4
            for s in sources[1:]:
                a=path.abspath(sources[0])
                b=path.abspath(s)
                start=0
                end=0
                for i in range(min(len(a),len(b))):
                    start=i
                    if a[i]!=b[i]:
                        break
                commonStart=min(commonStart,start)
                for i in range(min(len(a),len(b))):
                    end=i
                    if a[-(i+1)]!=b[-(i+1)]:
                        break
                commonEnd=min(commonEnd,end)
            diffs=[]
            for s in sources:
                b=path.abspath(s)
                if commonEnd>0:
                    diffs.append(b[commonStart:-(commonEnd)])
                else:
                    diffs.append(b[commonStart:])

        names=None
        title=path.splitext(path.basename(sources[0]))[0]
        if self.opts.namesFromFilename:
            names=path.splitext(path.basename(sources[0]))[0].split("_")
            title=None

        data=SpreadsheetData(names=names,
                             timeName=self.opts.time,
                             validData=self.opts.columns,
                             validMatchRegexp=self.opts.columnsRegexp,
                             title=title,
                             **self.dataFormatOptions(sources[0]))
        rawData=[deepcopy(data)]
        self.printColumns(sources[0],data)
        self.recalcColumns(data)
        self.rawAddColumns(data)

        if self.opts.time==None:
            self.opts.time=data.timeName()

        if not diffs[0] is None:
            data.rename(lambda c:diffs[0]+" "+c)

        for i,s in enumerate(sources[1:]):
            names=None
            title=path.splitext(path.basename(s))[0]
            if self.opts.namesFromFilename:
                names=title.split("_")
                title=None
            sData=SpreadsheetData(names=names,
                                  timeName=self.opts.time,
                                  validData=self.opts.columns,
                                  validMatchRegexp=self.opts.columnsRegexp,
                                  title=title,
                                  **self.dataFormatOptions(s))
            rawData.append(sData)
            self.printColumns(s,sData)
            self.recalcColumns(sData)
            self.rawAddColumns(sData)

            if self.opts.addTimes:
                data.addTimes(time=self.opts.time,
                               times=sData.data[self.opts.time],
                               interpolate=self.opts.interpolateNewTime)
            for n in sData.names():
                if n!=self.opts.time and (self.opts.columns==[] or data.validName(n,self.opts.columns,True)):
                    d=data.resample(sData,
                                    n,
                                    time=self.opts.time,
                                    extendData=self.opts.extendData,
                                    noInterpolation=not self.opts.newDataInterpolate)
                    data.append(diffs[i+1]+" "+n,d)

        self.joinedAddColumns(data)
        data.rename(self.processName,renameTime=True)
        data.rename(lambda c:c.strip())

        if len(sources)>1:
            self.printColumns("written data",data)

        if self.opts.automaticFormat:
            if self.getDataFormat(dest)=="excel":
                self.opts.writeExcel=True

        if self.opts.writeExcel:
            from pandas import ExcelWriter
            with ExcelWriter(dest) as writer:
                data.getData().to_excel(writer)
                if self.opts.addSheets:
                    for n,d in enumerate(rawData):
                        d.getData().to_excel(writer,
                                             sheet_name="Original file %d" % n)
        else:
            data.writeCSV(dest,
                          delimiter=self.opts.delimiter)

# Should work with Python3 and Python2
