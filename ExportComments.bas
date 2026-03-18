Sub ExportComments()
    Dim doc As Document
    Dim cmt As Comment
    Dim para As Paragraph
    Dim filePath As String
    Dim fileNum As Integer
    Dim cmtText As String
    Dim scopeText As String
    Dim i As Integer

    Set doc = ActiveDocument

    ' Guard: unsaved document has no path
    If doc.Path = "" Then
        MsgBox "Please save the document first before running this macro.", vbExclamation
        Exit Sub
    End If

    ' Guard: no comments to export
    If doc.Comments.Count = 0 Then
        MsgBox "This document contains no comments.", vbInformation
        Exit Sub
    End If

    filePath = doc.Path & "\" & "comments_export.txt"
    fileNum = FreeFile

    On Error GoTo ErrHandler
    Open filePath For Output As #fileNum

    Print #fileNum, "COMMENT EXPORT - " & doc.Name
    Print #fileNum, "Exported: " & Now()
    Print #fileNum, String(60, "-")

    i = 1
    For Each cmt In doc.Comments
        ' Collect comment body text across all paragraphs in the comment
        cmtText = ""
        For Each para In cmt.Range.Paragraphs
            cmtText = cmtText & para.Range.Text
        Next para

        ' Strip trailing paragraph marks, cell markers, and soft returns
        cmtText = Trim(Replace(cmtText, Chr(13), " "))
        cmtText = Trim(Replace(cmtText, Chr(7), ""))
        cmtText = Trim(Replace(cmtText, Chr(11), " "))

        ' Safely read the scope (anchored text in the document)
        scopeText = ""
        On Error Resume Next
        scopeText = Trim(cmt.Scope.Text)
        On Error GoTo ErrHandler
        If scopeText = "" Then scopeText = "(scope unavailable)"

        Print #fileNum, ""
        Print #fileNum, "Comment #" & i
        Print #fileNum, "Author:    " & cmt.Author
        Print #fileNum, "Date:      " & cmt.Date
        Print #fileNum, "Ref Text:  " & scopeText
        Print #fileNum, "Comment:   " & cmtText
        Print #fileNum, String(40, "-")

        i = i + 1
    Next cmt

    Close #fileNum
    MsgBox "Exported " & doc.Comments.Count & " comment(s) to:" & vbCrLf & filePath, vbInformation
    Exit Sub

ErrHandler:
    Close #fileNum
    MsgBox "Error " & Err.Number & ": " & Err.Description, vbCritical
End Sub
