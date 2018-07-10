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
    
    In case the deviation is EGATIVE the correction will stop at the frame before the deviation start a positive trend
    In case the deviation is POSITIVE the correction will stop at the frame before the deviation starts a negative trend 
    
    Parameters:
        <dict> selectedKeyFrameDict {selectedFrameID: value, ...}
        <bool> isPositiveDeviated whether the selected deviation is positive or negative
    
    Return int
    """
    
    
    if not selectedKeyFrameDict: return None
    
    sortedKeyIDList = sorted(selectedKeyFrameDict)
    print sortedKeyIDList
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
    


def runTool():
    try:
        del undoManager
    except:
        pass
        
    selectedCtrls = FBModelList()
    FBGetSelectedModels(selectedCtrls, None, True, True)
    
    animationChannels = ["Translation", "Rotation"]
    
       
    for control in selectedCtrls:
    
        for channel in animationChannels:
            exec "animationNodes = control.{0}.GetAnimationNode().Nodes".format(channel)
            for axis in range(3):
                animation_FCurveKeyList = animationNodes[axis].FCurve.Keys
                selectedKeyFrame_dict = getSelectedKeyFrameDict(animation_FCurveKeyList)
                if len(selectedKeyFrame_dict) < 2: continue
                
                sortedSelectedKeysID_list = sorted(selectedKeyFrame_dict) 
                
                ## evaluate deviation sign
                firstFrameID = sortedSelectedKeysID_list[0]
                predeviationFrameID = firstFrameID - 1
                
                ## figure out deviation of the curve
                positiveDeviation = True if animation_FCurveKeyList[firstFrameID].Value > animation_FCurveKeyList[predeviationFrameID].Value else False
         
                ## figure out correction point
                correctionStopFrame = getCorrectionLimit(selectedKeyFrame_dict, positiveDeviation)
                
                ## sift dictionary of the selected frames up to the correctionStopFrame
                for i in range(correctionStopFrame + 1, sortedSelectedKeysID_list[-1] + 1):
                    selectedKeyFrame_dict.pop(i)
    
                ## calculate deviation
                deltaDeviation =  getBeginDeviationDelta(animation_FCurveKeyList, sortedSelectedKeysID_list[0])
                
                ## normalize the selection
                normalizedDeviation_dict = normalizeDeviation(selectedKeyFrame_dict, sortedSelectedKeysID_list[0])
                
                ## perform offset
                offsetDeviation(animation_FCurveKeyList, selectedKeyFrame_dict, deltaDeviation, normalizedDeviation_dict)
   


 
# Define what the "DoIt" button does when clicked
def BtnCallbackDoIt(control, event):
    runTool()
    print "do it!"
 
 
# Start of the tool window lay out
def PopulateTool(t):
    #populate regions here
 
# Layout for the Button

    DoIt = FBButton()
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
    

    b = FBButton()
    b.Caption = "Offset"
    b.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(b,60)
    #b.OnClick.Add(BtnCallback)

    b = FBButton()
    b.Caption = "Closest Apex"
    b.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(b,60)
    #b.OnClick.Add(BtnCallback)  
    
    b = FBButton()
    b.Caption = "Whole Selection"
    b.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(b,60)
    
    b = FBButton()
    b.Caption = "Sadashige"
    b.Justify = FBTextJustify.kFBTextJustifyCenter
    lyt.AddRelative(b,60)

    """
    t.SetControl("DoIt", DoIt)
    DoIt.Visible = True
    DoIt.ReadOnly = False
    DoIt.Enabled = True
    # hover over the button and this msg. will apear
    DoIt.Hint = "launches what ever script you are testing - NOT FOR PRODUCTION"
    # the text that will appear on the button
    DoIt.Caption = "Fix Curve"
    DoIt.State = 0
    # the button style - read up on this, there are lots of functions to be had
    DoIt.Style = FBButtonStyle.kFBPushButton
    # the button's text will be centered
    DoIt.Justify = FBTextJustify.kFBTextJustifyCenter
    DoIt.Look = FBButtonLook.kFBLookNormal
    # this tells the button "when you are clicked go to def BtnCallbackDoIt"
    DoIt.OnClick.Add(BtnCallbackDoIt)
    """
     
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
    t.StartSizeY = 120
    PopulateTool(t)
    ShowTool(t)
    
    
CreateTool()