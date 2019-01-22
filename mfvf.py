# The prototype conversion script for NanoMine data vf-mf conversion
# Bingyin Hu 10/04/2018
from lxml import etree as ET
import os

class mfvfConvert:
    def __init__(self, filename):
        # read the xml
        self.tree = ET.parse(filename)
        self.filename = os.path.splitext(filename)[0] + '_mfvf.xml'
        # get the Matrix and the Filler elements
        self.mats = self.tree.findall('.//MatrixComponent')
        self.fils = self.tree.findall('.//Filler')
        self.matConsNum = len(self.mats) # number of Matrix constituent
        self.filNum = len(self.fils) # number of Filler
        # intermediate parameters
        self.filMV = '' # 'mass' or 'volume', base filler fraction
        self.matComp = 1 # Matrix composition, must be computed after determining the filler composition
        # downstream parameters
        self.matInfo = {} # an info dict for Matrix
        self.filInfo = {} # an info dict for Filler
        self.matMass = 0 # total mass of Matrix
        self.filMass = 0 # total mass of Filler
        self.matVol = 0 # total volume of Matrix
        self.filVol = 0 # total volume of Filler
        self.filMVs = [] # a list for labeling mass or volume FillerComposition for all fillers
        self.filComps = [] # a list for the actual values matching the filMVs list

    # this function is for cases when the density if not reported
    # we requires the density info to be stored in g/cm^3
    def getDensity(self, chemical):
        # someDensityFunction crawler?(TODO)
        density = someDensityFunction(chemical)
        return density

    # this function returns the most frequent items within a list
    def freq(self, myList):
        output = []
        frequency = {}
        for i in myList:
            if i not in frequency:
                frequency[i] = 0
            frequency[i] += 1
        most = max(frequency.values()) # the highest occurrence
        for j in frequency:
            if frequency[j] == most:
                output.append(j)
        return output

    # this function computes the absolute mass and volume of all 
    # filler components and saves them in self.filInfo
    def computeFiller(self):
        # loop thru the fillers
        for fil in xrange(self.filNum):
            filConInfo = {} # an info dict for FillerComponent, should be a value of self.filInfo. Example: self.filInfo[0] = filConInfo
            ele = self.fils[fil]
            # find all the FillerComponent under Filler
            filCons = ele.findall('.//FillerComponent')
            filConsNum = len(filCons)
            # record the FillerComposition
            c_ele = ele.find('.//FillerComposition/Fraction')
            if c_ele is not None:
                # see if it's mass or volume
                if c_ele.findtext('mass') is not None:
                    filMV = 'mass'
                    filComp = float(c_ele.findtext('mass'))
                elif c_ele.findtext('volume') is not None:
                    filMV = 'volume'
                    filComp = float(c_ele.findtext('volume'))
                else:
                    raise LookupError('[Filler Error] FillerComposition requires at least a "mass" field or a "volume" field.')
                self.filMVs.append(filMV)
                self.filComps.append(filComp)
            else:
                raise LookupError('[Filler Error] FillerComposition is missing.')
            # loop thru the filler components
            for filCon in filCons:
                # chemical name
                chemical = filCon.findtext('.//ChemicalName')
                if chemical is None or chemical == '':
                    raise LookupError('[Filler Error] Filler requires a non-empty chemical name.')
                # density (required to be in the form of g/cm^3)
                    # check whether value exists (TODO)
                    # check whether unit is g/cm^3 (TODO)
                    # need more layers here
                density = filCon.findtext('./Density/value') # one filler component should have only one density
                if density is None:
                    density = self.getDensity(chemical)
                else:
                    density = float(density)
                # filler component composition (TODO allow mf FCC under vf FC and vf FCC under mf FC)
                cc_ele = filCon.find('.//FillerComponentComposition/' + filMV)
                if cc_ele is None:
                    if filConsNum > 1:
                        raise AssertionError('[Filler Error] For fillers with multiple filler components, a filler component composition is required for each of the filler component.')
                    else:
                        mv = filMV
                        cc = 1.0 * filComp
                else:
                    mv = filMV
                    cc = float(cc_ele.text) * filComp
                # save everything for this filler component
                if mv == 'mass':
                    filConInfo[str(filCon)] = {'ChemicalName': chemical,
                                               'Density': density,
                                               'absMass': cc,
                                               'absVolume': cc/density}
                elif mv == 'volume':
                    filConInfo[str(filCon)] = {'ChemicalName': chemical,
                                               'Density': density,
                                               'absVolume': cc,
                                               'absMass': cc*density}
            # end of the loop thru the filler components
            # check total absMass or absVolume
            absMassSum = 0
            absVolSum = 0
            for i in filConInfo:
                absMassSum += filConInfo[i]['absMass'] # calculated for overall absMass
                absVolSum += filConInfo[i]['absVolume'] # calculated for overall absVolume
            if filMV == 'mass' and abs(absMassSum - filComp) >= 1e-5:
                raise AssertionError('[Filler Error] The sum of the filler component composition does not match the No.'+str(fil)+' filler composition.')
            elif filMV == 'volume' and abs(absVolSum - filComp) >= 1e-5:
                raise AssertionError('[Filler Error] The sum of the filler component composition does not match the No.'+str(fil)+' filler composition.')
            # pass the check, save to the self.filInfo
            self.filInfo[fil] = {'components': filConInfo}
            # add the overall filler info to filInfo[fil]
            self.filInfo[fil]['overall'] = {'absVolume': absVolSum,
                                            'absMass': absMassSum,
                                            filMV: filComp}
        # end of the loop thru the fillers
        # (TODO) allow filMV to have both mass and volume (requires solving er yuan yi ci equations)
        if len(set(self.filMVs)) > 1:
            raise AssertionError('[Filler Error] The filler compositions are not consistent. Some use mass while others use volume.')
        self.filMV = self.freq(self.filMVs)[0] # get the most frequently occurred fraction type (TODO need to move to the top, we are now assuming the self.filVM (mass or volume) of the composite has a total value of 1, if one of the filVM is not consistent, we cannot use the same method to compute cc)
        # compute the total filler composition (assuming filMVs are consistent)
        for filler in self.filInfo:
            self.filMass += self.filInfo[filler]['overall']['absMass']
            self.filVol += self.filInfo[filler]['overall']['absVolume']
        # compute the matrix composition
        if self.filMV == 'mass':
            self.matComp = 1 - self.filMass
        elif self.filMV == 'volume':
            self.matComp = 1 - self.filVol

    # this function computes the absolute mass and volume of all 
    # matrix components and saves them in self.matInfo
    def computeMatrix(self):
        for mat in xrange(self.matConsNum):
            ele = self.mats[mat]
            # chemical name
            chemical = ele.findtext('.//ChemicalName')
            if chemical is None or chemical == '':
                raise LookupError('[Matrix Error] Matrix requires a non-empty chemical name.')
            # check the number of density and MCC
            # 1 MatrixComponent should only have no more than 1 density value
            densitys = ele.findall('.//Density/value') # should be <= 1 element
            # only consider MCC with Fraction reported
            MCCs = ele.findall('.//MatrixComponentComposition/Fraction')
            # need to find a solution for block-polymers (TODO)
            if (len(densitys) == 1 and len(MCCs) == 0) or (len(densitys) - len(MCCs) == 0):
                pass
            else:
                raise AssertionError('[Matrix Error] The number of density provided does not match with the number of MatrixComponentComposition or Constituent.')
            # density (required to be in the form of g/cm^3)
                # check whether value exists (TODO)
                # check whether unit is g/cm^3 (TODO)
                # need more layers here
            density = ele.findtext('.//Density/value')
            if density is None:
                density = self.getDensity(chemical)
            else:
                density = float(density)
            # matrix component composition
            cc_ele = ele.find('.//MatrixComponentComposition/Fraction')
            if cc_ele is None:
                mv = self.filMV
                cc = 1.0 * self.matComp
            else:
                # see if it's mass or volume and if it's consistent with self.filMV (TODO allow MCC to be different with self.filMV)
                if cc_ele.findtext('mass') is not None:
                    if self.filMV != 'mass':
                        raise AssertionError('[Matrix Error] MatrixComponentComposition type is not consistent with FillerComposition.')
                    mv = self.filMV
                    cc = float(cc_ele.findtext('mass')) * self.matComp
                elif cc_ele.findtext('volume') is not None:
                    if self.filMV != 'volume':
                        raise AssertionError('[Matrix Error] MatrixComponentComposition type is not consistent with FillerComposition.')
                    mv = self.filMV
                    cc = float(cc_ele.findtext('volume')) * self.matComp
                else:
                    raise LookupError('[Matrix Error] MatrixComponentComposition requires at least a "mass" field or a "volume" field.')
            # save everything for this matrix component
            if mv == 'mass':
                self.matInfo[mat] = {'ChemicalName': chemical,
                                          'Density': density,
                                          'absMass': cc,
                                          'absVolume': cc/density,
                                          mv: cc}
            elif mv == 'volume':
                self.matInfo[mat] = {'ChemicalName': chemical,
                                          'Density': density,
                                          'absVolume': cc,
                                          'absMass': cc*density,
                                          mv: cc}
            else:
                raise ValueError('[Matrix Error] Cannot determine the fraction type for the matrix.')
        # end of the loop
        # check total absMass or absVolume
        absMassSum = 0
        absVolSum = 0
        for i in self.matInfo:
            absMassSum += self.matInfo[i]['absMass']
            absVolSum += self.matInfo[i]['absVolume']
        self.matMass = absMassSum # save to self.matMass
        self.matVol = absVolSum # save to self.matVol
        if self.filMV == 'mass' and abs(absMassSum - self.matComp) >= 1e-5:
            raise AssertionError('[Matrix Error] The sum of the matrix component composition does not match the result by subtracting the filler composition from 1.')
        elif self.filMV == 'volume' and abs(absVolSum - self.matComp) >= 1e-5:
            raise AssertionError('[Matrix Error] The sum of the matrix component composition does not match the result by subtracting the filler composition from 1.')
        # pass the check, add the overall matrix info to self.matInfo
        self.matInfo['overall'] = {'absVolume': absVolSum,
                                   'absMass': absMassSum}

    # this function computes the missing mf and vf based on self.matInfo and self.filInfo, then inserts into xmls
    def computeComposite(self):
        totalAbsMass = self.matMass + self.filMass
        totalAbsVol = self.matVol + self.filVol
        # loop thru the fillers in self.filInfo
        for fil in xrange(self.filNum):
            # preparation for insertion back into xmls
            ele = self.fils[fil]
            c_ele = ele.find('.//FillerComposition/Fraction')
            # compute mf and vf, if any of them exists, double-check
            mf = self.filInfo[fil]['overall']['absMass'] / float(totalAbsMass)
            vf = self.filInfo[fil]['overall']['absVolume'] / float(totalAbsVol)
            # mass fraction
            if 'mass' in self.filInfo[fil]['overall']:
                if abs(self.filInfo[fil]['overall']['mass'] - mf) >= 1e-2:
                    raise AssertionError('[Calculation Error] The calculated mass fraction of filler No.'+str(fil)+' is not consistent with the reported value.')
            else:
                self.filInfo[fil]['overall']['mass'] = mf
                c_ele.insert(0, ET.Element('mass'))
                c_ele.find('.//mass').text = str(mf)
            # volume fraction
            if 'volume' in self.filInfo[fil]['overall']:
                if abs(self.filInfo[fil]['overall']['volume'] - vf) >= 1e-2:
                    raise AssertionError('[Calculation Error] The calculated volume fraction of filler No.'+str(fil)+' is not consistent with the reported value.')
            else:
                self.filInfo[fil]['overall']['volume'] = vf
                c_ele.insert(-1, ET.Element('volume'))
                c_ele.find('.//volume').text = str(vf)
    
    # this function writes the tree to the filename
    def writeTree(self):
        root = self.tree.getroot()
        et = ET.ElementTree(root)
        et.write(self.filename, pretty_print=True, xml_declaration=True, encoding="utf-8")

    # this function calls the appropriate functions to finish the whole conversion process
    def run(self):
        if self.tree.find('.//MATERIALS/Filler') is None:
            return # pure polymer
        self.computeFiller()
        self.computeMatrix()
        self.computeComposite()
        self.writeTree()

## Test
if __name__ == '__main__':
    # mvc = mfvfConvert('test.xml')
    mvc = mfvfConvert('corner2.xml')
    mvc.run()