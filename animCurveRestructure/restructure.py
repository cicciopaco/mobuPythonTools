import uuid


from pyfbsdk import *
from pyfbsdk_additions import *


def getSelectedKeyFrameDict(FBKeyList):
    """
    Extract from the FBFCurve provied a dictionary containing
    id and value per every key frame of the curve
    Parameters:
        FBPropertyListFCurveKey
    
    Returns
        Dictionary {keyFrameId: keyFrameValue, ...}

    """
    if not FBKeyList:
        return
    keyFramesDict = {}
    for i in range(len(FBKeyList)):
        if FBKeyList[i].Selected:
            keyFramesDict[i] = FBKeyList[i].Value
            
    return keyFramesDict


def getCorrectionLimit(selectedKeyFrameDict, isPositiveDeviated):
    """
    returns the index of the frame where to stop the curve correction.
    
    In case the deviation is NEGATIVE the correction will stop at the frame before the deviation start a positive trend
    In case the deviation is POSITIVE the correction will stop at the frame before the deviation starts a negative trend 
    
    Parameters:
        <dict> selectedKeyFrameDict {selectedFrameID: value, ...}
        <bool> isPositiveDeviated whether the selected deviation is positive or negative
    
    Return int
    """
    
    
    if not selectedKeyFrameDict: return None
    
    sortedKeyIDList = sorted(selectedKeyFrameDict)
    refValue = selectedKeyFrameDict[sortedKeyIDList[0]]
    
    if len(selectedKeyFrameDict) < 2: return sortedKeyIDList[0]
    
    if isPositiveDeviated:
        for i in range(1, len(sortedKeyIDList)):
            if selectedKeyFrameDict[sortedKeyIDList[i]] < refValue:
                return sortedKeyIDList[i-1]
            else:
                refValue = selectedKeyFrameDict[sortedKeyIDList[i]]
    

    else:
        for i in range(1, len(sortedKeyIDList)):
            if selectedKeyFrameDict[sortedKeyIDList[i]] > refValue:
                return sortedKeyIDList[i-1]
            else:
                refValue = selectedKeyFrameDict[sortedKeyIDList[i]]
    
    return sortedKeyIDList[-1]

    
def getBeginDeviationDelta(FCurveKeyList, keyReferenceID):
    """
    Returns the delta of the deviation between the beginning of the selection and 
    the regular trend of the animation curve before the selection
    
    Parameters:
        FBPropertyListFCurveKey FCurveKeyList
        int keyReferenceID
    
    Returns:
        float
    """
    
    # get in a tuple ID and Value of the TWO frames before the deviation (selected keyframes)
    pointA = (keyReferenceID-1, FCurveKeyList[keyReferenceID-1].Value )
    pointB = (keyReferenceID-2, FCurveKeyList[keyReferenceID-2].Value )

    
    # calculate slope and y intercept of the animation curve before the deviation
    slope = (pointA[1] - pointB[1]) / (pointA[0] - pointB[0])
    intercept = pointA[1] - (pointA[0] * slope)

    # get estimation of the next frame value based on the regular animation curve
    estimatedSelectedKeyFrameValue = (slope * keyReferenceID) + intercept 

    
    # calculated delta of the deviation
    return estimatedSelectedKeyFrameValue - FCurveKeyList[keyReferenceID].Value

    
def normalizeDeviation(selectedFrames_dict, referenceFrameID):
    """
    Returns a normalized copy of the provided dictionary pivoting around the provided
    frame reference
    
    Paramaters:
        dict selectedFramesDict
        string referenceFrameID
    
    Return:
        dict
    """
    
    selectionMinVal = sorted(selectedFrames_dict.values())[0]
    selectionMaxVal = sorted(selectedFrames_dict.values())[-1]
    selectionAverage = 0
    for value in selectedFrames_dict.values():
        selectionAverage += value
    selectionAverage /= len(selectedFrames_dict.values())
    
    referenceFrameValue = selectedFrames_dict[referenceFrameID]

    
    # establish normalization in function of the reference frame (first frame)
    selectionMinVal = selectionMinVal if referenceFrameValue >= selectionAverage else selectionMaxVal
    selectionMaxVal = referenceFrameValue
    
    
    selectedFramesNormValue_dict = {}
    for key, value in selectedFrames_dict.items():
        selectedFramesNormValue_dict[key] = (value - selectionMinVal) / (selectionMaxVal - selectionMinVal)
    
    return selectedFramesNormValue_dict


def offsetDeviation(FCurveKeyList, sortedSelectedKeysID_list, deviationDelta, normalizedDeviation_dict = None):
    # apply delta to the deviation (offset the whole animation chunck about the same factor)
    if normalizedDeviation_dict:
        for key in sortedSelectedKeysID_list:
            FCurveKeyList[key].Value += deviationDelta * normalizedDeviation_dict[key]
        return

                
    for key in sortedSelectedKeysID_list:
        FCurveKeyList[key].Value += deviationDelta


def extractSlope(fCurve, onSelecction=False):
    """
    return a list containig the slope values of each copy of keyframe contained in the
    provided FBFcurve
    :param fCurve: FBFCurve
    :return:
    """

    keysList = fCurve.Keys
    if len(keysList) < 2 : return None

    fTimeMode = FBPlayerControl().GetTransportFps()
    slopeList = []
    keyID = 0
    while keyID < len(keysList) - 1:

        slopeList.append((keysList[keyID+1].Value - keysList[keyID].Value) / (keysList[keyID+1].Time.GetFrame(fTimeMode) - keysList[keyID].Time.GetFrame(fTimeMode)))
        keyID += 1

    return slopeList


def extractSpikes(fCurve, deviationFactor = 1.0, onSelection=False):
    """
    Returns a list containing the ID of the keyframe of the given FBFcurve
    that represent a deviation from the animation curve trend defined by the average
    of the slope variation between pair of contiguous keyframes multiplied by tbe
    specified deviation factor.
    For convenience add the id of the last frame to the end of the list so to facilitate
    the definition of the anomaly intervals
    Parameters:
        FBFcurve fCurve
        int deviationFactor: factor used to multiply the de average slope variation of the curve
    Return
        list of int (keyframes id that exceed the deviation threshold)
    """

    slopesCollection = extractSlope(fCurve, onSelection)

    if not slopesCollection : return []

    fTimeMode = FBPlayerControl().GetTransportFps()
    spikes = []
    deviationThreshold = 0.0
    for slope in slopesCollection:
        deviationThreshold += abs(slope)
    deviationThreshold /= len(slopesCollection)
    deviationThreshold *= deviationFactor


    for i, slope in enumerate(slopesCollection):
        if abs(slope) > deviationThreshold : spikes.append(fCurve.Keys[i].Time.GetFrame()+1)

    spikes.append(fCurve.Keys[len(fCurve.Keys) - 1].Time.GetFrame(fTimeMode))

    return spikes

def groupAnomalies(spikesList):
    """
    Analyzes the spikes list and defines the intervals of keyframes to correct
    Parameters:
        list spikesList
    Return:
        list of tuples of int: [(anomalyBegin, anomalyEnd), ...]
    """

    i = 0
    n = 2
    anomaliesGroups = []
    while i < len(spikesList)/2:
        anomaliesGroups.append((spikesList[n*i], spikesList[(n*i)+1]))
        i += 1

    return anomaliesGroups



def runTool(mode = 0):
    try:
        del undoManager
    except:
        pass
        
    selectedCtrls = FBModelList()
    FBGetSelectedModels(selectedCtrls, None, True, True)
    
    animationChannels = ["Translation", "Rotation"]

    undoManager = FBUndoManager()

    undoManager.TransactionBegin(str(uuid.uuid1()))


    for control in selectedCtrls:

        undoManager.TransactionAddModelTRS(control)
    
        for channel in animationChannels:
            exec "animationNodes = control.{0}.GetAnimationNode().Nodes".format(channel)
            for axis in range(3):
                animation_FCurveKeyList = animationNodes[axis].FCurve.Keys
                selectedKeyFrame_dict = getSelectedKeyFrameDict(animation_FCurveKeyList)
                if len(selectedKeyFrame_dict) < 2: continue
                
                sortedSelectedKeysID_list = sorted(selectedKeyFrame_dict) 

                if mode == 1:

                    ## evaluate deviation sign
                    firstFrameID = sortedSelectedKeysID_list[0]
                    predeviationFrameID = firstFrameID - 1

                    isDeviationPositive = True if animation_FCurveKeyList[firstFrameID].Value > animation_FCurveKeyList[predeviationFrameID].Value else False

                    ## figure out correction point
                    correctionStopFrame = getCorrectionLimit(selectedKeyFrame_dict, isDeviationPositive)

                    ## sift dictionary of the selected frames up to the correctionStopFrame
                    for i in range(correctionStopFrame + 1, sortedSelectedKeysID_list[-1] + 1):
                        selectedKeyFrame_dict.pop(i)


                ## calculate deviation
                deltaDeviation =  getBeginDeviationDelta(animation_FCurveKeyList, sortedSelectedKeysID_list[0])



                if mode == 1 or mode == 2:

                    ## normalize the selection
                    normalizedDeviation_dict = normalizeDeviation(selectedKeyFrame_dict, sortedSelectedKeysID_list[0])

                    ## perform offset
                    offsetDeviation(animation_FCurveKeyList, selectedKeyFrame_dict, deltaDeviation, normalizedDeviation_dict)

                elif mode == 0:
                    offsetDeviation(animation_FCurveKeyList, selectedKeyFrame_dict, deltaDeviation)


                elif mode == 3:

                    ## get coordinates of the selection
                    x_gappedL = sortedSelectedKeysID_list[0]
                    x_gappedR = sortedSelectedKeysID_list[-1]

                    x_delta = x_gappedR - x_gappedL

                    y_gappedL = selectedKeyFrame_dict[x_gappedL]
                    y_gappedR = selectedKeyFrame_dict[x_gappedR]

                    print x_gappedL, y_gappedL
                    print x_gappedR, y_gappedR

                    ## get pre and post deviation values
                    ## NOTICE: provide a system to avoid to go beyond the last keyframe
                    x_preDeviation = x_gappedL - 1
                    y_preDeviation = animation_FCurveKeyList[x_preDeviation].Value

                    x_postDeviation = x_gappedR + 1
                    y_postDeviation = animation_FCurveKeyList[x_postDeviation].Value


                    print x_preDeviation, y_preDeviation
                    print x_postDeviation, y_postDeviation

                    preSlope = extractSlope(animationNodes[axis].FCurve)[x_preDeviation - 1]
                    postSlope = extractSlope(animationNodes[axis].FCurve)[x_postDeviation]

                    print preSlope, postSlope

                    preIntercept = y_preDeviation / (preSlope * x_preDeviation)
                    postIntercept = y_postDeviation / (postSlope * x_postDeviation)

                    y_expectedL = (x_gappedL * preSlope) + preIntercept
                    y_expectedR = (x_gappedR * postSlope) + postIntercept

                    y_deltaL = y_gappedL - y_expectedL
                    y_deltaR = y_gappedR - y_expectedR

                    for key in sortedSelectedKeysID_list:
                        preFactor = float((key - x_gappedL) - x_delta) / float(0-x_delta)
                        postFactor  = float((key - x_gappedL) - 0) / float(x_delta-0)

                        print preFactor, postFactor

                        animation_FCurveKeyList[key].Value += (y_deltaL * preFactor) - (y_deltaR * postFactor)




                    weightedCorrection = {}


                    # y_expectedL =
                    # pre_m = (animation_FCurveKeyList[-1].Value - animation_FCurveKeyList[-2].Value) / (animation_FCurveKeyList[-1].Time - animation_FCurveKeyList[-2].Time)
                    # post_m =




                    ## calculalte delta of the first frame

                    ##


    undoManager.TransactionEnd()

 

 
 
# Start of the tool window lay out
def PopulateTool(t):
    #populate regions here
 
# Layout for the Button

    # the DoIt button's position on the x
    x = FBAddRegionParam(15,FBAttachType.kFBAttachLeft,"")
    # the DoIt button's position on the y
    y = FBAddRegionParam(10,FBAttachType.kFBAttachTop,"")
    # the DoIt button's width
    w = FBAddRegionParam(-15,FBAttachType.kFBAttachRight,"")
    # the DoIt button's height
    h = FBAddRegionParam(-10,FBAttachType.kFBAttachBottom,"")
    
    
    t.AddRegion("DoIt","DoIt", x, y, w, h)
    lyt = FBVBoxLayout()
    t.SetControl("DoIt",lyt)
    

    offsetBtn = FBButton()
    offsetBtn.Caption = "Offset"
    offsetBtn.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(offsetBtn,60)
    offsetBtn.OnClick.Add(offsetCB)

    closetApexBtn = FBButton()
    closetApexBtn.Caption = "Closest Apex"
    closetApexBtn.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(closetApexBtn,60)
    closetApexBtn.OnClick.Add(closetApexCB)
    
    wholeSelectionBtn = FBButton()
    wholeSelectionBtn.Caption = "Whole Selection"
    wholeSelectionBtn.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(wholeSelectionBtn,60)
    wholeSelectionBtn.OnClick.Add(wholeSelectionCB)
    
    ishanBtn = FBButton()
    ishanBtn.Caption = "ishan method"
    ishanBtn.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(ishanBtn,60)
    ishanBtn.OnClick.Add(ishanCB)


def offsetCB(*args,**kwargs):
    runTool(0)

def closetApexCB(*args,**kwargs):
    runTool(1)

def wholeSelectionCB(*args,**kwargs):
    runTool(2)

def ishanCB(*args,**kwargs):
    runTool(3)


def CreateTool():
    # the tool window's name
    try:
        del t
    except:
        pass 
    t = FBCreateUniqueTool("CurveTool Proto")
    # the tool window's width
    t.StartSizeX = 200
    # the tool window's height
    t.StartSizeY = 350
    PopulateTool(t)
    ShowTool(t)
    
    
CreateTool()