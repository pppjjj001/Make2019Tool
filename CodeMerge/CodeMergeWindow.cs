using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;
using System.Linq;

namespace CodeMerge
{
    public class CodeMergeWindow : EditorWindow
    {
        // 文件路径
        private string _baseFilePath = "";
        private string _localFilePath = "";
        private string _remoteFilePath = "";
        private string _outputFilePath = "";
        
        // 文件内容
        private string _baseContent = "";
        private string _localContent = "";
        private string _remoteContent = "";
        
        // 合并结果
        private MergeResult _mergeResult;
        
        // UI状态
        private Vector2 _scrollPosition;
        private Vector2 _leftScrollPos;
        private Vector2 _middleScrollPos;
        private Vector2 _rightScrollPos;
        private bool _syncScroll = true;
        private int _viewMode = 0; // 0=三栏, 1=两栏对比, 2=统一视图
        private int _selectedConflict = -1;
        
        // 编辑状态
        private Dictionary<int, string> _manualEdits = new Dictionary<int, string>();
        private bool _showLineNumbers = true;
        private bool _showDiffOnly = false;
        
        [MenuItem("Tools/TempByAI/Code Merge/Code Merge Tool")]
        public static void ShowWindow()
        {
            var window = GetWindow<CodeMergeWindow>("Code Merge");
            window.minSize = new Vector2(1000, 600);
        }
        
        private void OnEnable()
        {
            MergeStyles.RefreshStyles();
        }

        private void OnGUI()
        {
            DrawToolbar();
            
            EditorGUILayout.Space(5);
            
            DrawFileSelection();
            
            EditorGUILayout.Space(5);
            
            if (_mergeResult != null)
            {
                DrawMergeStatus();
                EditorGUILayout.Space(5);
                DrawMergeView();
                EditorGUILayout.Space(5);
                DrawConflictNavigation();
            }
        }

        #region Toolbar
        
        private void DrawToolbar()
        {
            EditorGUILayout.BeginHorizontal(EditorStyles.toolbar);
            
            if (GUILayout.Button("Load Files", EditorStyles.toolbarButton, GUILayout.Width(80)))
            {
                LoadFiles();
            }
            
            if (GUILayout.Button("Merge", EditorStyles.toolbarButton, GUILayout.Width(60)))
            {
                PerformMerge();
            }
            
            GUILayout.Space(10);
            
            EditorGUI.BeginDisabledGroup(_mergeResult == null);
            
            if (GUILayout.Button("Save Result", EditorStyles.toolbarButton, GUILayout.Width(80)))
            {
                SaveResult();
            }
            
            if (GUILayout.Button("Auto Resolve", EditorStyles.toolbarButton, GUILayout.Width(80)))
            {
                AutoResolveConflicts();
            }
            
            EditorGUI.EndDisabledGroup();
            
            GUILayout.FlexibleSpace();
            
            // 视图选项
            EditorGUILayout.LabelField("View:", GUILayout.Width(35));
            _viewMode = EditorGUILayout.Popup(_viewMode, new[] { "Three-Way", "Side by Side", "Unified" }, 
                EditorStyles.toolbarPopup, GUILayout.Width(100));
            
            GUILayout.Space(10);
            
            _showLineNumbers = GUILayout.Toggle(_showLineNumbers, "Line #", EditorStyles.toolbarButton);
            _showDiffOnly = GUILayout.Toggle(_showDiffOnly, "Diff Only", EditorStyles.toolbarButton);
            _syncScroll = GUILayout.Toggle(_syncScroll, "Sync Scroll", EditorStyles.toolbarButton);
            
            EditorGUILayout.EndHorizontal();
        }
        
        #endregion

        #region File Selection
        
        private void DrawFileSelection()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("File Selection", EditorStyles.boldLabel);
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Base (Ancestor):", GUILayout.Width(120));
            _baseFilePath = EditorGUILayout.TextField(_baseFilePath);
            if (GUILayout.Button("...", GUILayout.Width(30)))
            {
                _baseFilePath = EditorUtility.OpenFilePanel("Select Base File", 
                    Application.dataPath, "cs,txt,json,xml");
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Local (Mine):", GUILayout.Width(120));
            _localFilePath = EditorGUILayout.TextField(_localFilePath);
            if (GUILayout.Button("...", GUILayout.Width(30)))
            {
                _localFilePath = EditorUtility.OpenFilePanel("Select Local File", 
                    Application.dataPath, "cs,txt,json,xml");
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Remote (Theirs):", GUILayout.Width(120));
            _remoteFilePath = EditorGUILayout.TextField(_remoteFilePath);
            if (GUILayout.Button("...", GUILayout.Width(30)))
            {
                _remoteFilePath = EditorUtility.OpenFilePanel("Select Remote File", 
                    Application.dataPath, "cs,txt,json,xml");
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Output:", GUILayout.Width(120));
            _outputFilePath = EditorGUILayout.TextField(_outputFilePath);
            if (GUILayout.Button("...", GUILayout.Width(30)))
            {
                _outputFilePath = EditorUtility.SaveFilePanel("Save Merged File", 
                    Application.dataPath, "merged", "cs");
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.EndVertical();
        }
        
        #endregion

        #region Merge Status
        
        private void DrawMergeStatus()
        {
            EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
            
            var totalBlocks = _mergeResult.Blocks.Count;
            var conflictCount = _mergeResult.ConflictCount;
            var unresolvedCount = _mergeResult.UnresolvedCount;
            
            var statusColor = unresolvedCount > 0 ? MergeStyles.ConflictColor : MergeStyles.AddedColor;
            var prevColor = GUI.color;
            GUI.color = statusColor;
            
            EditorGUILayout.LabelField($"Status: {(unresolvedCount > 0 ? "Has Conflicts" : "Ready to Save")}", 
                EditorStyles.boldLabel, GUILayout.Width(200));
            
            GUI.color = prevColor;
            
            EditorGUILayout.LabelField($"Total Blocks: {totalBlocks}", GUILayout.Width(120));
            EditorGUILayout.LabelField($"Conflicts: {conflictCount}", GUILayout.Width(100));
            EditorGUILayout.LabelField($"Unresolved: {unresolvedCount}", GUILayout.Width(100));
            
            GUILayout.FlexibleSpace();
            
            EditorGUILayout.EndHorizontal();
        }
        
        #endregion

        #region Merge View
        
        private void DrawMergeView()
        {
            switch (_viewMode)
            {
                case 0:
                    DrawThreeWayView();
                    break;
                case 1:
                    DrawSideBySideView();
                    break;
                case 2:
                    DrawUnifiedView();
                    break;
            }
        }
        
        private void DrawThreeWayView()
        {
            EditorGUILayout.BeginHorizontal();
            
            // 左栏 - Local
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 3 - 10));
            DrawColumnHeader("LOCAL (Mine)", MergeStyles.AddedColor);
            _leftScrollPos = EditorGUILayout.BeginScrollView(_leftScrollPos, 
                GUILayout.Height(position.height - 250));
            
            DrawMergeBlocks(0);
            
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            // 中栏 - Merged Result
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 3 - 10));
            DrawColumnHeader("MERGED RESULT", Color.white);
            _middleScrollPos = EditorGUILayout.BeginScrollView(_middleScrollPos, 
                GUILayout.Height(position.height - 250));
            
            DrawMergeBlocks(1);
            
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            // 右栏 - Remote
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 3 - 10));
            DrawColumnHeader("REMOTE (Theirs)", MergeStyles.RemovedColor);
            _rightScrollPos = EditorGUILayout.BeginScrollView(_rightScrollPos, 
                GUILayout.Height(position.height - 250));
            
            DrawMergeBlocks(2);
            
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.EndHorizontal();
            
            // 同步滚动
            if (_syncScroll)
            {
                SyncScrollPositions();
            }
        }
        
        private void DrawSideBySideView()
        {
            EditorGUILayout.BeginHorizontal();
            
            // 左栏 - Local
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 2 - 10));
            DrawColumnHeader("LOCAL", MergeStyles.AddedColor);
            _leftScrollPos = EditorGUILayout.BeginScrollView(_leftScrollPos, 
                GUILayout.Height(position.height - 250));
            DrawMergeBlocks(0);
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            // 右栏 - Remote
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 2 - 10));
            DrawColumnHeader("REMOTE", MergeStyles.RemovedColor);
            _rightScrollPos = EditorGUILayout.BeginScrollView(_rightScrollPos, 
                GUILayout.Height(position.height - 250));
            DrawMergeBlocks(2);
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.EndHorizontal();
            
            if (_syncScroll)
            {
                SyncScrollPositions();
            }
        }
        
        private void DrawUnifiedView()
        {
            _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition, 
                GUILayout.Height(position.height - 200));
            
            int lineNo = 1;
            for (int i = 0; i < _mergeResult.Blocks.Count; i++)
            {
                var block = _mergeResult.Blocks[i];
                
                if (block.IsConflict)
                {
                    DrawConflictBlock(i, block, ref lineNo);
                }
                else
                {
                    foreach (var line in block.MergedContent)
                    {
                        DrawCodeLine(lineNo++, line, DiffType.Equal);
                    }
                }
            }
            
            EditorGUILayout.EndScrollView();
        }
        
        private void DrawColumnHeader(string title, Color color)
        {
            var rect = EditorGUILayout.GetControlRect(false, 25);
            var prevColor = GUI.color;
            GUI.color = color;
            GUI.Box(rect, "", EditorStyles.helpBox);
            GUI.color = prevColor;
            
            GUI.Label(rect, title, MergeStyles.HeaderStyle);
        }
        
        private void DrawMergeBlocks(int column)
        {
            int lineNo = 1;
            
            for (int i = 0; i < _mergeResult.Blocks.Count; i++)
            {
                var block = _mergeResult.Blocks[i];
                
                List<string> lines;
                switch (column)
                {
                    case 0: // Local
                        lines = block.LocalContent.Count > 0 ? block.LocalContent : block.MergedContent;
                        break;
                    case 1: // Merged
                        lines = block.IsResolved || !block.IsConflict ? 
                            block.MergedContent : new List<string> { "<<< CONFLICT >>>" };
                        break;
                    case 2: // Remote
                        lines = block.RemoteContent.Count > 0 ? block.RemoteContent : block.MergedContent;
                        break;
                    default:
                        lines = block.MergedContent;
                        break;
                }
                
                if (_showDiffOnly && !block.IsConflict && 
                    block.LocalContent.SequenceEqual(block.RemoteContent))
                {
                    lineNo += lines.Count;
                    continue;
                }
                
                var diffType = DiffType.Equal;
                if (block.IsConflict)
                    diffType = DiffType.Modified;
                else if (block.LocalContent.Count != block.RemoteContent.Count ||
                         !block.LocalContent.SequenceEqual(block.RemoteContent))
                    diffType = column == 0 ? DiffType.Added : DiffType.Removed;
                
                foreach (var line in lines)
                {
                    if (block.IsConflict)
                    {
                        DrawConflictLine(i, lineNo++, line, column);
                    }
                    else
                    {
                        DrawCodeLine(lineNo++, line, diffType);
                    }
                }
                
                // 如果是冲突块，在中间栏显示解决按钮
                if (block.IsConflict && column == 1)
                {
                    DrawConflictResolutionButtons(i, block);
                }
            }
        }
        
        private void DrawCodeLine(int lineNo, string content, DiffType diffType)
        {
            EditorGUILayout.BeginHorizontal();
            
            if (_showLineNumbers)
            {
                EditorGUILayout.LabelField(lineNo.ToString(), MergeStyles.LineNumberStyle, 
                    GUILayout.Width(40));
            }
            
            GUIStyle style;
            switch (diffType)
            {
                case DiffType.Added:
                    style = MergeStyles.AddedLineStyle;
                    break;
                case DiffType.Removed:
                    style = MergeStyles.RemovedLineStyle;
                    break;
                case DiffType.Modified:
                    style = MergeStyles.ConflictLineStyle;
                    break;
                default:
                    style = MergeStyles.CodeStyle;
                    break;
            }
            
            EditorGUILayout.SelectableLabel(content, style, GUILayout.Height(18));
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void DrawConflictLine(int blockIndex, int lineNo, string content, int column)
        {
            var isSelected = _selectedConflict == blockIndex;
            
            EditorGUILayout.BeginHorizontal();
            
            if (_showLineNumbers)
            {
                var prevColor = GUI.color;
                GUI.color = isSelected ? MergeStyles.ConflictColor : Color.gray;
                EditorGUILayout.LabelField(lineNo.ToString(), MergeStyles.LineNumberStyle, 
                    GUILayout.Width(40));
                GUI.color = prevColor;
            }
            
            EditorGUILayout.SelectableLabel(content, MergeStyles.ConflictLineStyle, GUILayout.Height(18));
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void DrawConflictBlock(int blockIndex, MergeBlock block, ref int lineNo)
        {
            var rect = EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField($"=== CONFLICT {blockIndex + 1} ===", EditorStyles.boldLabel);
            
            EditorGUILayout.LabelField("LOCAL:", EditorStyles.miniBoldLabel);
            foreach (var line in block.LocalContent)
            {
                DrawCodeLine(lineNo++, line, DiffType.Added);
            }
            
            EditorGUILayout.LabelField("REMOTE:", EditorStyles.miniBoldLabel);
            foreach (var line in block.RemoteContent)
            {
                DrawCodeLine(lineNo++, line, DiffType.Removed);
            }
            
            DrawConflictResolutionButtons(blockIndex, block);
            
            EditorGUILayout.EndVertical();
        }
        
        private void DrawConflictResolutionButtons(int blockIndex, MergeBlock block)
        {
            EditorGUILayout.BeginHorizontal();
            
            if (GUILayout.Button("Take Local", GUILayout.Height(20)))
            {
                MergeEngine.ResolveConflict(block, ConflictResolution.TakeLocal);
                Repaint();
            }
            
            if (GUILayout.Button("Take Remote", GUILayout.Height(20)))
            {
                MergeEngine.ResolveConflict(block, ConflictResolution.TakeRemote);
                Repaint();
            }
            
            if (GUILayout.Button("Take Both", GUILayout.Height(20)))
            {
                MergeEngine.ResolveConflict(block, ConflictResolution.TakeBoth);
                Repaint();
            }
            
            if (GUILayout.Button("Edit", GUILayout.Height(20)))
            {
                ShowManualEditDialog(blockIndex, block);
            }
            
            EditorGUILayout.EndHorizontal();
        }
        
        #endregion

        #region Conflict Navigation
        
        private void DrawConflictNavigation()
        {
            if (_mergeResult.ConflictCount == 0) return;
            
            EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("Navigate Conflicts:", GUILayout.Width(120));
            
            if (GUILayout.Button("◀ Previous", GUILayout.Width(100)))
            {
                NavigateToConflict(-1);
            }
            
            if (GUILayout.Button("Next ▶", GUILayout.Width(100)))
            {
                NavigateToConflict(1);
            }
            
            GUILayout.Space(20);
            
            EditorGUILayout.LabelField($"Current: {_selectedConflict + 1} / {_mergeResult.ConflictCount}",
                GUILayout.Width(120));
            
            GUILayout.FlexibleSpace();
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void NavigateToConflict(int direction)
        {
            var conflictIndices = _mergeResult.Blocks
                .Select((b, i) => (block: b, index: i))
                .Where(x => x.block.IsConflict)
                .Select(x => x.index)
                .ToList();
            
            if (conflictIndices.Count == 0) return;
            
            int currentIdx = conflictIndices.IndexOf(_selectedConflict);
            if (currentIdx == -1)
            {
                _selectedConflict = conflictIndices[0];
            }
            else
            {
                currentIdx += direction;
                if (currentIdx < 0) currentIdx = conflictIndices.Count - 1;
                if (currentIdx >= conflictIndices.Count) currentIdx = 0;
                _selectedConflict = conflictIndices[currentIdx];
            }
            
            Repaint();
        }
        
        #endregion

        #region Operations
        
        private void LoadFiles()
        {
            try
            {
                if (!string.IsNullOrEmpty(_baseFilePath) && File.Exists(_baseFilePath))
                    _baseContent = File.ReadAllText(_baseFilePath);
                else
                    _baseContent = "";
                
                if (!string.IsNullOrEmpty(_localFilePath) && File.Exists(_localFilePath))
                    _localContent = File.ReadAllText(_localFilePath);
                else
                    _localContent = "";
                
                if (!string.IsNullOrEmpty(_remoteFilePath) && File.Exists(_remoteFilePath))
                    _remoteContent = File.ReadAllText(_remoteFilePath);
                else
                    _remoteContent = "";
                
                if (string.IsNullOrEmpty(_outputFilePath))
                    _outputFilePath = _localFilePath;
                
                EditorUtility.DisplayDialog("Success", "Files loaded successfully!", "OK");
            }
            catch (System.Exception e)
            {
                EditorUtility.DisplayDialog("Error", $"Failed to load files: {e.Message}", "OK");
            }
        }
        
        private void PerformMerge()
        {
            if (string.IsNullOrEmpty(_baseContent) && 
                string.IsNullOrEmpty(_localContent) && 
                string.IsNullOrEmpty(_remoteContent))
            {
                EditorUtility.DisplayDialog("Error", "Please load files first!", "OK");
                return;
            }
            
            _mergeResult = MergeEngine.ThreeWayMerge(_baseContent, _localContent, _remoteContent);
            _selectedConflict = _mergeResult.ConflictCount > 0 ? 0 : -1;
            _manualEdits.Clear();
            
            Repaint();
        }
        
        private void SaveResult()
        {
            if (_mergeResult == null) return;
            
            if (_mergeResult.HasConflicts)
            {
                if (!EditorUtility.DisplayDialog("Warning", 
                    $"There are {_mergeResult.UnresolvedCount} unresolved conflicts. Save anyway?",
                    "Yes", "No"))
                {
                    return;
                }
            }
            
            string path = _outputFilePath;
            if (string.IsNullOrEmpty(path))
            {
                path = EditorUtility.SaveFilePanel("Save Merged File", 
                    Application.dataPath, "merged", "cs");
            }
            
            if (!string.IsNullOrEmpty(path))
            {
                try
                {
                    File.WriteAllText(path, _mergeResult.GetMergedContent());
                    AssetDatabase.Refresh();
                    EditorUtility.DisplayDialog("Success", "File saved successfully!", "OK");
                }
                catch (System.Exception e)
                {
                    EditorUtility.DisplayDialog("Error", $"Failed to save file: {e.Message}", "OK");
                }
            }
        }
        
        private void AutoResolveConflicts()
        {
            if (_mergeResult == null) return;
            
            int resolved = 0;
            foreach (var block in _mergeResult.Blocks)
            {
                if (block.IsConflict && !block.IsResolved)
                {
                    // 自动解决策略：
                    // 1. 如果本地为空，取远程
                    // 2. 如果远程为空，取本地
                    // 3. 否则保持冲突
                    
                    if (block.LocalContent.Count == 0)
                    {
                        MergeEngine.ResolveConflict(block, ConflictResolution.TakeRemote);
                        resolved++;
                    }
                    else if (block.RemoteContent.Count == 0)
                    {
                        MergeEngine.ResolveConflict(block, ConflictResolution.TakeLocal);
                        resolved++;
                    }
                }
            }
            
            EditorUtility.DisplayDialog("Auto Resolve", 
                $"Automatically resolved {resolved} conflict(s).\n" +
                $"Remaining conflicts: {_mergeResult.UnresolvedCount}", "OK");
            
            Repaint();
        }
        
        private void ShowManualEditDialog(int blockIndex, MergeBlock block)
        {
            ManualEditWindow.ShowWindow(block, () =>
            {
                Repaint();
            });
        }
        
        private void SyncScrollPositions()
        {
            // 检测哪个面板在滚动，同步其他面板
            if (_leftScrollPos != _middleScrollPos || _leftScrollPos != _rightScrollPos)
            {
                // 简单策略：以最后改变的为准
                _middleScrollPos = _leftScrollPos;
                _rightScrollPos = _leftScrollPos;
            }
        }
        
        #endregion
    }
    
    /// <summary>
    /// 手动编辑窗口
    /// </summary>
    public class ManualEditWindow : EditorWindow
    {
        private MergeBlock _block;
        private string _editContent;
        private System.Action _onSave;
        private Vector2 _scrollPos;
        
        public static void ShowWindow(MergeBlock block, System.Action onSave)
        {
            var window = GetWindow<ManualEditWindow>("Manual Edit");
            window._block = block;
            window._editContent = string.Join("\n", 
                block.MergedContent.Count > 0 ? block.MergedContent : block.LocalContent);
            window._onSave = onSave;
            window.minSize = new Vector2(600, 400);
            window.ShowUtility();
        }
        
        private void OnGUI()
        {
            EditorGUILayout.BeginVertical();
            
            EditorGUILayout.LabelField("Reference - Local:", EditorStyles.boldLabel);
            EditorGUILayout.BeginVertical(EditorStyles.helpBox, GUILayout.Height(80));
            foreach (var line in _block.LocalContent)
            {
                EditorGUILayout.LabelField(line, MergeStyles.AddedLineStyle);
            }
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.LabelField("Reference - Remote:", EditorStyles.boldLabel);
            EditorGUILayout.BeginVertical(EditorStyles.helpBox, GUILayout.Height(80));
            foreach (var line in _block.RemoteContent)
            {
                EditorGUILayout.LabelField(line, MergeStyles.RemovedLineStyle);
            }
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.Space(10);
            
            EditorGUILayout.LabelField("Edit Merged Content:", EditorStyles.boldLabel);
            _scrollPos = EditorGUILayout.BeginScrollView(_scrollPos, GUILayout.ExpandHeight(true));
            _editContent = EditorGUILayout.TextArea(_editContent, GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
            
            EditorGUILayout.Space(10);
            
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Save", GUILayout.Height(30)))
            {
                var lines = _editContent.Split('\n');
                MergeEngine.ResolveConflict(_block, ConflictResolution.Manual, lines);
                _onSave?.Invoke();
                Close();
            }
            if (GUILayout.Button("Cancel", GUILayout.Height(30)))
            {
                Close();
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.EndVertical();
        }
    }
}
