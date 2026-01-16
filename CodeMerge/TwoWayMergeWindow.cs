using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;
using System.Linq;

namespace CodeMerge
{
    public class TwoWayMergeWindow : EditorWindow
    {
        #region Fields
        
        // 文件路径
        private string _baseFilePath = "";
        private string _localFilePath = "";
        private string _outputFilePath = "";
        
        // 文件内容
        private string _baseContent = "";
        private string _localContent = "";
        
        // 合并结果
        private TwoWayMergeResult _mergeResult;
        
        // 保留选项
        private PreserveOptions _preserveOptions = PreserveOptions.ClassName;
        private bool _showPreserveOptions = true;
        
        // UI状态
        private Vector2 _leftScrollPos;
        private Vector2 _rightScrollPos;
        private Vector2 _resultScrollPos;
        private Vector2 _previewScrollPos;
        private bool _syncScroll = true;
        private int _viewMode = 0; // 0=双栏对比, 1=结果预览, 2=统一视图
        private bool _showLineNumbers = true;
        private bool _showDiffOnly = false;
        private int _selectedDiff = -1;
        
        // 名称映射预览
        private Dictionary<string, string> _nameChangesPreview;
        private bool _showNameChangesPreview = false;
        
        // Tab状态
        private int _currentTab = 0;
        private string[] _tabNames = { "Merge", "Name Changes", "Settings" };
        
        #endregion

        [MenuItem("Tools/TempByAI/Code Merge/Two-Way Merge Tool")]
        public static void ShowWindow()
        {
            var window = GetWindow<TwoWayMergeWindow>("Two-Way Merge");
            window.minSize = new Vector2(900, 600);
        }
        
        private void OnEnable()
        {
            MergeStyles.RefreshStyles();
        }

        private void OnGUI()
        {
            DrawToolbar();
            
            EditorGUILayout.Space(5);
            
            _currentTab = GUILayout.Toolbar(_currentTab, _tabNames, GUILayout.Height(25));
            
            EditorGUILayout.Space(5);
            
            switch (_currentTab)
            {
                case 0:
                    DrawMergeTab();
                    break;
                case 1:
                    DrawNameChangesTab();
                    break;
                case 2:
                    DrawSettingsTab();
                    break;
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
            
            if (GUILayout.Button("Smart Merge", EditorStyles.toolbarButton, GUILayout.Width(90)))
            {
                PerformSmartMerge();
            }
            
            GUILayout.Space(10);
            
            EditorGUI.BeginDisabledGroup(_mergeResult == null);
            
            if (GUILayout.Button("Save Result", EditorStyles.toolbarButton, GUILayout.Width(80)))
            {
                SaveResult();
            }
            
            if (GUILayout.Button("Copy to Clipboard", EditorStyles.toolbarButton, GUILayout.Width(110)))
            {
                CopyToClipboard();
            }
            
            EditorGUI.EndDisabledGroup();
            
            GUILayout.FlexibleSpace();
            
            // 快速保留选项
            var prevColor = GUI.backgroundColor;
            GUI.backgroundColor = _preserveOptions.HasFlag(PreserveOptions.ClassName) ? 
                new Color(0.5f, 0.8f, 0.5f) : Color.white;
            
            if (GUILayout.Toggle(_preserveOptions.HasFlag(PreserveOptions.ClassName), 
                "Keep Base Class Names", EditorStyles.toolbarButton, GUILayout.Width(130)))
            {
                _preserveOptions |= PreserveOptions.ClassName;
            }
            else
            {
                _preserveOptions &= ~PreserveOptions.ClassName;
            }
            
            GUI.backgroundColor = prevColor;
            
            EditorGUILayout.EndHorizontal();
        }
        
        #endregion

        #region Merge Tab
        
        private void DrawMergeTab()
        {
            DrawFileSelection();
            
            EditorGUILayout.Space(5);
            
            if (_mergeResult != null)
            {
                DrawMergeStatus();
                EditorGUILayout.Space(5);
                
                // 视图模式选择
                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField("View Mode:", GUILayout.Width(70));
                _viewMode = GUILayout.Toolbar(_viewMode, new[] { "Side by Side", "Result Preview", "Unified" }, 
                    GUILayout.Width(300));
                
                GUILayout.FlexibleSpace();
                
                _showLineNumbers = GUILayout.Toggle(_showLineNumbers, "Line #", EditorStyles.miniButton);
                _showDiffOnly = GUILayout.Toggle(_showDiffOnly, "Diff Only", EditorStyles.miniButton);
                _syncScroll = GUILayout.Toggle(_syncScroll, "Sync Scroll", EditorStyles.miniButton);
                
                EditorGUILayout.EndHorizontal();
                
                EditorGUILayout.Space(5);
                
                DrawMergeView();
                
                EditorGUILayout.Space(5);
                
                DrawDiffNavigation();
            }
        }
        
        private void DrawFileSelection()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("File Selection", EditorStyles.boldLabel);
            
            // Base文件
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Base File:", GUILayout.Width(80));
            _baseFilePath = EditorGUILayout.TextField(_baseFilePath);
            if (GUILayout.Button("Browse", GUILayout.Width(60)))
            {
                string path = EditorUtility.OpenFilePanel("Select Base File", 
                    GetInitialDirectory(), "cs,txt,json,xml,js,ts");
                if (!string.IsNullOrEmpty(path)) _baseFilePath = path;
            }
            if (GUILayout.Button("From Selection", GUILayout.Width(100)))
            {
                var selected = Selection.activeObject;
                if (selected != null)
                {
                    _baseFilePath = AssetDatabase.GetAssetPath(selected);
                    _baseFilePath = Path.GetFullPath(_baseFilePath);
                }
            }
            EditorGUILayout.EndHorizontal();
            
            // Local文件
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Local File:", GUILayout.Width(80));
            _localFilePath = EditorGUILayout.TextField(_localFilePath);
            if (GUILayout.Button("Browse", GUILayout.Width(60)))
            {
                string path = EditorUtility.OpenFilePanel("Select Local File", 
                    GetInitialDirectory(), "cs,txt,json,xml,js,ts");
                if (!string.IsNullOrEmpty(path)) _localFilePath = path;
            }
            if (GUILayout.Button("From Clipboard", GUILayout.Width(100)))
            {
                _localContent = GUIUtility.systemCopyBuffer;
                EditorUtility.DisplayDialog("Info", "Content loaded from clipboard.", "OK");
            }
            EditorGUILayout.EndHorizontal();
            
            // 输出文件
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Output:", GUILayout.Width(80));
            _outputFilePath = EditorGUILayout.TextField(_outputFilePath);
            if (GUILayout.Button("Browse", GUILayout.Width(60)))
            {
                string path = EditorUtility.SaveFilePanel("Save Merged File", 
                    GetInitialDirectory(), "merged", "cs");
                if (!string.IsNullOrEmpty(path)) _outputFilePath = path;
            }
            if (GUILayout.Button("= Base", GUILayout.Width(50)))
            {
                _outputFilePath = _baseFilePath;
            }
            if (GUILayout.Button("= Local", GUILayout.Width(50)))
            {
                _outputFilePath = _localFilePath;
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.EndVertical();
        }
        
        private void DrawMergeStatus()
        {
            EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
            
            var diffCount = _mergeResult.DifferenceCount;
            var replacementCount = _mergeResult.NameReplacements.Count;
            
            EditorGUILayout.LabelField($"Differences: {diffCount}", GUILayout.Width(120));
            
            if (replacementCount > 0)
            {
                var prevColor = GUI.color;
                GUI.color = MergeStyles.ModifiedColor;
                EditorGUILayout.LabelField($"Name Replacements: {replacementCount}", GUILayout.Width(150));
                GUI.color = prevColor;
            }
            
            // 显示当前使用的保留选项
            var options = new List<string>();
            if (_preserveOptions.HasFlag(PreserveOptions.ClassName)) options.Add("Class");
            if (_preserveOptions.HasFlag(PreserveOptions.StructName)) options.Add("Struct");
            if (_preserveOptions.HasFlag(PreserveOptions.InterfaceName)) options.Add("Interface");
            if (_preserveOptions.HasFlag(PreserveOptions.EnumName)) options.Add("Enum");
            if (_preserveOptions.HasFlag(PreserveOptions.Namespace)) options.Add("Namespace");
            
            if (options.Count > 0)
            {
                EditorGUILayout.LabelField($"Preserving: {string.Join(", ", options)}");
            }
            
            GUILayout.FlexibleSpace();
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void DrawMergeView()
        {
            switch (_viewMode)
            {
                case 0:
                    DrawSideBySideView();
                    break;
                case 1:
                    DrawResultPreviewView();
                    break;
                case 2:
                    DrawUnifiedView();
                    break;
            }
        }
        
        private void DrawSideBySideView()
        {
            float viewHeight = position.height - 280;
            
            EditorGUILayout.BeginHorizontal();
            
            // 左栏 - Base
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 2 - 15));
            DrawColumnHeader("BASE (Original)", new Color(0.6f, 0.6f, 0.8f));
            _leftScrollPos = EditorGUILayout.BeginScrollView(_leftScrollPos, GUILayout.Height(viewHeight));
            DrawMergeBlocksColumn(true);
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            // 分隔线
            DrawVerticalSeparator(viewHeight);
            
            // 右栏 - Local (Merged)
            EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 2 - 15));
            DrawColumnHeader("LOCAL (Modified) → Merged", MergeStyles.AddedColor);
            _rightScrollPos = EditorGUILayout.BeginScrollView(_rightScrollPos, GUILayout.Height(viewHeight));
            DrawMergeBlocksColumn(false);
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.EndHorizontal();
            
            if (_syncScroll)
            {
                SyncScrollPositions();
            }
        }
        
        private void DrawResultPreviewView()
        {
            float viewHeight = position.height - 280;
            
            DrawColumnHeader("MERGED RESULT PREVIEW", Color.white);
            _resultScrollPos = EditorGUILayout.BeginScrollView(_resultScrollPos, GUILayout.Height(viewHeight));
            
            int lineNo = 1;
            foreach (var block in _mergeResult.Blocks)
            {
                var lines = block.MergedLines.Count > 0 ? block.MergedLines :
                    (block.UseLocal ? block.LocalLines : block.BaseLines);
                
                foreach (var line in lines)
                {
                    if (_showDiffOnly && block.Type == DiffType.Equal) 
                    {
                        lineNo++;
                        continue;
                    }
                    
                    DrawCodeLine(lineNo++, line, block.Type, block.UseLocal);
                }
            }
            
            EditorGUILayout.EndScrollView();
        }
        
        private void DrawUnifiedView()
        {
            float viewHeight = position.height - 280;
            
            _resultScrollPos = EditorGUILayout.BeginScrollView(_resultScrollPos, GUILayout.Height(viewHeight));
            
            int baseLineNo = 1;
            int localLineNo = 1;
            
            for (int i = 0; i < _mergeResult.Blocks.Count; i++)
            {
                var block = _mergeResult.Blocks[i];
                
                if (_showDiffOnly && block.Type == DiffType.Equal)
                {
                    baseLineNo += block.BaseLines.Count;
                    localLineNo += block.LocalLines.Count;
                    continue;
                }
                
                if (block.Type != DiffType.Equal)
                {
                    // 显示差异块
                    DrawUnifiedDiffBlock(i, block, ref baseLineNo, ref localLineNo);
                }
                else
                {
                    // 显示相同内容
                    foreach (var line in block.BaseLines)
                    {
                        DrawUnifiedLine(baseLineNo++, localLineNo++, line, DiffType.Equal);
                    }
                }
            }
            
            EditorGUILayout.EndScrollView();
        }
        
        private void DrawMergeBlocksColumn(bool isBaseColumn)
        {
            int lineNo = 1;
            
            for (int i = 0; i < _mergeResult.Blocks.Count; i++)
            {
                var block = _mergeResult.Blocks[i];
                var lines = isBaseColumn ? block.BaseLines : block.LocalLines;
                
                if (_showDiffOnly && block.Type == DiffType.Equal)
                {
                    lineNo += lines.Count;
                    continue;
                }
                
                // 差异块高亮
                if (block.Type != DiffType.Equal)
                {
                    var rect = EditorGUILayout.BeginVertical();
                    
                    // 背景色
                    Color bgColor;
                    if (isBaseColumn)
                    {
                        bgColor = block.Type == DiffType.Removed ? 
                            new Color(0.3f, 0.5f, 0.3f, 0.2f) : // 被替换
                            new Color(0.5f, 0.3f, 0.3f, 0.2f);  // 被删除
                    }
                    else
                    {
                        bgColor = block.Type == DiffType.Added ?
                            new Color(0.3f, 0.5f, 0.3f, 0.2f) : // 新增
                            new Color(0.3f, 0.5f, 0.3f, 0.2f);  // 替换内容
                    }
                    
                    EditorGUI.DrawRect(rect, bgColor);
                    
                    // 选择按钮（仅在Local栏显示）
                    if (!isBaseColumn && block.Type != DiffType.Equal)
                    {
                        EditorGUILayout.BeginHorizontal();
                        
                        var prevColor = GUI.backgroundColor;
                        GUI.backgroundColor = block.UseLocal ? MergeStyles.AddedColor : Color.gray;
                        
                        if (GUILayout.Button(block.UseLocal ? "✓ Using Local" : "Use Local", 
                            GUILayout.Width(100), GUILayout.Height(18)))
                        {
                            block.UseLocal = true;
                            block.MergedLines.Clear();
                            block.MergedLines.AddRange(block.LocalLines);
                        }
                        
                        GUI.backgroundColor = !block.UseLocal ? MergeStyles.RemovedColor : Color.gray;
                        
                        if (GUILayout.Button(!block.UseLocal ? "✓ Using Base" : "Use Base", 
                            GUILayout.Width(100), GUILayout.Height(18)))
                        {
                            block.UseLocal = false;
                            block.MergedLines.Clear();
                            block.MergedLines.AddRange(block.BaseLines);
                        }
                        
                        GUI.backgroundColor = prevColor;
                        
                        GUILayout.FlexibleSpace();
                        EditorGUILayout.EndHorizontal();
                    }
                }
                else
                {
                    EditorGUILayout.BeginVertical();
                }
                
                // 显示行内容
                foreach (var line in lines)
                {
                    var diffType = block.Type;
                    if (isBaseColumn && diffType == DiffType.Added)
                        diffType = DiffType.Equal; // Base侧没有新增内容，显示为空
                    if (!isBaseColumn && diffType == DiffType.Removed)
                        diffType = DiffType.Equal; // Local侧没有删除内容，显示为空
                    
                    DrawCodeLine(lineNo++, line, diffType, !isBaseColumn && block.UseLocal);
                }
                
                // 如果一侧没有内容，添加占位
                if (lines.Count == 0 && block.Type != DiffType.Equal)
                {
                    var otherLines = isBaseColumn ? block.LocalLines : block.BaseLines;
                    for (int j = 0; j < otherLines.Count; j++)
                    {
                        DrawEmptyLine(lineNo++);
                    }
                }
                
                EditorGUILayout.EndVertical();
            }
        }
        
        private void DrawUnifiedDiffBlock(int blockIndex, TwoWayMergeBlock block, 
            ref int baseLineNo, ref int localLineNo)
        {
            var rect = EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            // 控制按钮
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField($"--- Diff Block {blockIndex + 1} ---", EditorStyles.boldLabel);
            
            GUILayout.FlexibleSpace();
            
            var prevColor = GUI.backgroundColor;
            GUI.backgroundColor = block.UseLocal ? MergeStyles.AddedColor : Color.gray;
            if (GUILayout.Button("Use Local", GUILayout.Width(80)))
            {
                block.UseLocal = true;
                block.MergedLines.Clear();
                block.MergedLines.AddRange(block.LocalLines);
            }
            
            GUI.backgroundColor = !block.UseLocal ? new Color(0.6f, 0.6f, 0.8f) : Color.gray;
            if (GUILayout.Button("Use Base", GUILayout.Width(80)))
            {
                block.UseLocal = false;
                block.MergedLines.Clear();
                block.MergedLines.AddRange(block.BaseLines);
            }
            GUI.backgroundColor = prevColor;
            
            EditorGUILayout.EndHorizontal();
            
            // Base内容（删除的）
            if (block.BaseLines.Count > 0)
            {
                EditorGUILayout.LabelField("Base:", EditorStyles.miniLabel);
                foreach (var line in block.BaseLines)
                {
                    DrawUnifiedLine(baseLineNo++, -1, "- " + line, DiffType.Removed);
                }
            }
            
            // Local内容（新增的）
            if (block.LocalLines.Count > 0)
            {
                EditorGUILayout.LabelField("Local:", EditorStyles.miniLabel);
                foreach (var line in block.LocalLines)
                {
                    DrawUnifiedLine(-1, localLineNo++, "+ " + line, DiffType.Added);
                }
            }
            
            EditorGUILayout.EndVertical();
        }
        
        private void DrawCodeLine(int lineNo, string content, DiffType diffType, bool isUsed = true)
        {
            EditorGUILayout.BeginHorizontal();
            
            if (_showLineNumbers)
            {
                var style = new GUIStyle(MergeStyles.LineNumberStyle);
                style.normal.textColor = isUsed ? Color.gray : new Color(0.5f, 0.5f, 0.5f, 0.5f);
                EditorGUILayout.LabelField(lineNo.ToString(), style, GUILayout.Width(40));
            }
            
            GUIStyle lineStyle;
            switch (diffType)
            {
                case DiffType.Added:
                    lineStyle = MergeStyles.AddedLineStyle;
                    break;
                case DiffType.Removed:
                    lineStyle = MergeStyles.RemovedLineStyle;
                    break;
                case DiffType.Modified:
                    lineStyle = MergeStyles.ConflictLineStyle;
                    break;
                default:
                    lineStyle = MergeStyles.CodeStyle;
                    break;
            }
            
            if (!isUsed)
            {
                lineStyle = new GUIStyle(lineStyle);
                lineStyle.normal.textColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
            }
            
            EditorGUILayout.SelectableLabel(content, lineStyle, GUILayout.Height(18));
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void DrawUnifiedLine(int baseLineNo, int localLineNo, string content, DiffType diffType)
        {
            EditorGUILayout.BeginHorizontal();
            
            if (_showLineNumbers)
            {
                string baseNum = baseLineNo > 0 ? baseLineNo.ToString() : "";
                string localNum = localLineNo > 0 ? localLineNo.ToString() : "";
                EditorGUILayout.LabelField(baseNum, MergeStyles.LineNumberStyle, GUILayout.Width(30));
                EditorGUILayout.LabelField(localNum, MergeStyles.LineNumberStyle, GUILayout.Width(30));
            }
            
            // GUIStyle lineStyle = diffType switch
            // {
            //     DiffType.Added => MergeStyles.AddedLineStyle,
            //     DiffType.Removed => MergeStyles.RemovedLineStyle,
            //     DiffType.Modified => MergeStyles.ConflictLineStyle,
            //     _ => MergeStyles.CodeStyle
            // };
            GUIStyle lineStyle;
            switch (diffType)
            {
                case DiffType.Added:
                    lineStyle = MergeStyles.AddedLineStyle;
                    break;
                case DiffType.Removed:
                    lineStyle = MergeStyles.RemovedLineStyle;
                    break;
                case DiffType.Modified:
                    lineStyle = MergeStyles.ConflictLineStyle;
                    break;
                default:
                    lineStyle = MergeStyles.CodeStyle;
                    break;
            }

            
            EditorGUILayout.SelectableLabel(content, lineStyle, GUILayout.Height(18));
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void DrawEmptyLine(int lineNo)
        {
            EditorGUILayout.BeginHorizontal();
            
            if (_showLineNumbers)
            {
                EditorGUILayout.LabelField("", MergeStyles.LineNumberStyle, GUILayout.Width(40));
            }
            
            var style = new GUIStyle(MergeStyles.CodeStyle);
            style.normal.background = MergeStyles.MakeTexture(new Color(0.3f, 0.3f, 0.3f, 0.1f));
            EditorGUILayout.LabelField("", style, GUILayout.Height(18));
            
            EditorGUILayout.EndHorizontal();
        }
        
        private void DrawVerticalSeparator(float height)
        {
            var rect = GUILayoutUtility.GetRect(2, height);
            EditorGUI.DrawRect(rect, new Color(0.3f, 0.3f, 0.3f));
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
        
        private void DrawDiffNavigation()
        {
            if (_mergeResult.DifferenceCount == 0) return;
            
            EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("Navigate Differences:", GUILayout.Width(130));
            
            if (GUILayout.Button("◀ Previous", GUILayout.Width(100)))
            {
                NavigateToDiff(-1);
            }
            
            if (GUILayout.Button("Next ▶", GUILayout.Width(100)))
            {
                NavigateToDiff(1);
            }
            
            GUILayout.Space(20);
            
            if (GUILayout.Button("Accept All Local", GUILayout.Width(120)))
            {
                AcceptAll(true);
            }
            
            if (GUILayout.Button("Accept All Base", GUILayout.Width(120)))
            {
                AcceptAll(false);
            }
            
            GUILayout.FlexibleSpace();
            
            EditorGUILayout.EndHorizontal();
        }
        
        #endregion

        #region Name Changes Tab
        
        private void DrawNameChangesTab()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("Name Preservation Options", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "These options allow you to keep the original names from the Base file " +
                "when merging with Local file changes.", MessageType.Info);
            
            EditorGUILayout.Space(10);
            
            // 保留选项
            EditorGUILayout.LabelField("Preserve Names:", EditorStyles.boldLabel);
            
            DrawPreserveOption("Class Names", PreserveOptions.ClassName);
            DrawPreserveOption("Struct Names", PreserveOptions.StructName);
            DrawPreserveOption("Interface Names", PreserveOptions.InterfaceName);
            DrawPreserveOption("Enum Names", PreserveOptions.EnumName);
            DrawPreserveOption("Delegate Names", PreserveOptions.DelegateName);
            DrawPreserveOption("Namespace", PreserveOptions.Namespace);
            
            EditorGUILayout.Space(10);
            
            // 快捷按钮
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Select All Types", GUILayout.Height(25)))
            {
                _preserveOptions = PreserveOptions.AllTypes;
            }
            if (GUILayout.Button("Select None", GUILayout.Height(25)))
            {
                _preserveOptions = PreserveOptions.None;
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.Space(10);
            
            // 预览名称变更
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Name Changes Preview", EditorStyles.boldLabel);
            
            if (GUILayout.Button("Detect Changes", GUILayout.Width(120)))
            {
                DetectNameChanges();
            }
            EditorGUILayout.EndHorizontal();
            
            if (_nameChangesPreview != null && _nameChangesPreview.Count > 0)
            {
                _previewScrollPos = EditorGUILayout.BeginScrollView(_previewScrollPos, 
                    GUILayout.Height(200));
                
                EditorGUILayout.BeginVertical();
                foreach (var kvp in _nameChangesPreview)
                {
                    EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
                    
                    var prevColor = GUI.color;
                    GUI.color = MergeStyles.RemovedColor;
                    EditorGUILayout.LabelField(kvp.Key, GUILayout.Width(200));
                    GUI.color = prevColor;
                    
                    EditorGUILayout.LabelField("→", GUILayout.Width(30));
                    
                    GUI.color = MergeStyles.AddedColor;
                    EditorGUILayout.LabelField(kvp.Value, GUILayout.Width(200));
                    GUI.color = prevColor;
                    
                    EditorGUILayout.EndHorizontal();
                }
                EditorGUILayout.EndVertical();
                
                EditorGUILayout.EndScrollView();
            }
            else if (_nameChangesPreview != null)
            {
                EditorGUILayout.HelpBox("No name changes detected between Base and Local files.", 
                    MessageType.Info);
            }
            
            // 显示合并后的名称替换
            if (_mergeResult != null && _mergeResult.NameReplacements.Count > 0)
            {
                EditorGUILayout.Space(10);
                EditorGUILayout.LabelField("Applied Replacements:", EditorStyles.boldLabel);
                
                foreach (var replacement in _mergeResult.NameReplacements)
                {
                    EditorGUILayout.BeginHorizontal();
                    EditorGUILayout.LabelField($"[{replacement.TypeKeyword}]", GUILayout.Width(80));
                    EditorGUILayout.LabelField(replacement.OriginalName, GUILayout.Width(150));
                    EditorGUILayout.LabelField("→", GUILayout.Width(30));
                    EditorGUILayout.LabelField(replacement.NewName, GUILayout.Width(150));
                    EditorGUILayout.LabelField($"(Line {replacement.LineNumber})", GUILayout.Width(80));
                    EditorGUILayout.EndHorizontal();
                }
            }
            
            EditorGUILayout.EndVertical();
        }
        
        private void DrawPreserveOption(string label, PreserveOptions option)
        {
            EditorGUILayout.BeginHorizontal();
            
            bool isEnabled = _preserveOptions.HasFlag(option);
            bool newValue = EditorGUILayout.Toggle(isEnabled, GUILayout.Width(20));
            
            if (newValue != isEnabled)
            {
                if (newValue)
                    _preserveOptions |= option;
                else
                    _preserveOptions &= ~option;
            }
            
            EditorGUILayout.LabelField(label);
            
            EditorGUILayout.EndHorizontal();
        }
        
        #endregion

        #region Settings Tab
        
        private void DrawSettingsTab()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("Display Settings", EditorStyles.boldLabel);
            
            _showLineNumbers = EditorGUILayout.Toggle("Show Line Numbers", _showLineNumbers);
            _showDiffOnly = EditorGUILayout.Toggle("Show Differences Only", _showDiffOnly);
            _syncScroll = EditorGUILayout.Toggle("Synchronize Scroll", _syncScroll);
            
            EditorGUILayout.Space(10);
            
            EditorGUILayout.LabelField("Default View Mode", EditorStyles.boldLabel);
            _viewMode = EditorGUILayout.Popup("View Mode", _viewMode, 
                new[] { "Side by Side", "Result Preview", "Unified" });
            
            EditorGUILayout.EndVertical();
            
            EditorGUILayout.Space(10);
            
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.LabelField("About", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "Two-Way Merge Tool\n\n" +
                "This tool allows you to merge changes from a Local file into a Base file, " +
                "with the option to preserve original class names and other identifiers from the Base file.\n\n" +
                "Features:\n" +
                "• Side-by-side comparison\n" +
                "• Selective merge (choose Base or Local for each change)\n" +
                "• Automatic name preservation\n" +
                "• Smart merge suggestions",
                MessageType.None);
            
            EditorGUILayout.EndVertical();
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
                else if (string.IsNullOrEmpty(_localContent))
                    _localContent = "";
                
                if (string.IsNullOrEmpty(_outputFilePath) && !string.IsNullOrEmpty(_baseFilePath))
                    _outputFilePath = _baseFilePath;
                
                // 自动检测名称变更
                DetectNameChanges();
                
                EditorUtility.DisplayDialog("Success", "Files loaded successfully!", "OK");
            }
            catch (System.Exception e)
            {
                EditorUtility.DisplayDialog("Error", $"Failed to load files: {e.Message}", "OK");
            }
        }
        
        private void PerformMerge()
        {
            if (string.IsNullOrEmpty(_baseContent) && string.IsNullOrEmpty(_localContent))
            {
                EditorUtility.DisplayDialog("Error", "Please load files first!", "OK");
                return;
            }
            
            _mergeResult = TwoWayMergeEngine.Merge(_baseContent, _localContent, _preserveOptions);
            _selectedDiff = _mergeResult.DifferenceCount > 0 ? 0 : -1;
            
            Repaint();
        }
        
        private void PerformSmartMerge()
        {
            if (string.IsNullOrEmpty(_baseContent) && string.IsNullOrEmpty(_localContent))
            {
                EditorUtility.DisplayDialog("Error", "Please load files first!", "OK");
                return;
            }
            
            _mergeResult = TwoWayMergeEngine.SmartMerge(_baseContent, _localContent, _preserveOptions);
            _selectedDiff = _mergeResult.DifferenceCount > 0 ? 0 : -1;
            
            Repaint();
        }
        
        private void SaveResult()
        {
            if (_mergeResult == null) return;
            
            string path = _outputFilePath;
            if (string.IsNullOrEmpty(path))
            {
                path = EditorUtility.SaveFilePanel("Save Merged File", 
                    GetInitialDirectory(), "merged", "cs");
            }
            
            if (!string.IsNullOrEmpty(path))
            {
                try
                {
                    File.WriteAllText(path, _mergeResult.GetMergedContent());
                    AssetDatabase.Refresh();
                    EditorUtility.DisplayDialog("Success", $"File saved to:\n{path}", "OK");
                }
                catch (System.Exception e)
                {
                    EditorUtility.DisplayDialog("Error", $"Failed to save file: {e.Message}", "OK");
                }
            }
        }
        
        private void CopyToClipboard()
        {
            if (_mergeResult == null) return;
            
            GUIUtility.systemCopyBuffer = _mergeResult.GetMergedContent();
            EditorUtility.DisplayDialog("Success", "Merged content copied to clipboard!", "OK");
        }
        
        private void DetectNameChanges()
        {
            if (string.IsNullOrEmpty(_baseContent) || string.IsNullOrEmpty(_localContent))
            {
                _nameChangesPreview = null;
                return;
            }
            
            _nameChangesPreview = TwoWayMergeEngine.PreviewNameChanges(_baseContent, _localContent);
        }
        
        private void NavigateToDiff(int direction)
        {
            var diffIndices = _mergeResult.Blocks
                .Select((b, i) => (block: b, index: i))
                .Where(x => x.block.HasDifference)
                .Select(x => x.index)
                .ToList();
            
            if (diffIndices.Count == 0) return;
            
            int currentIdx = diffIndices.IndexOf(_selectedDiff);
            if (currentIdx == -1)
            {
                _selectedDiff = diffIndices[0];
            }
            else
            {
                currentIdx += direction;
                if (currentIdx < 0) currentIdx = diffIndices.Count - 1;
                if (currentIdx >= diffIndices.Count) currentIdx = 0;
                _selectedDiff = diffIndices[currentIdx];
            }
            
            Repaint();
        }
        
        private void AcceptAll(bool useLocal)
        {
            foreach (var block in _mergeResult.Blocks)
            {
                if (block.HasDifference)
                {
                    block.UseLocal = useLocal;
                    block.MergedLines.Clear();
                    block.MergedLines.AddRange(useLocal ? block.LocalLines : block.BaseLines);
                }
            }
            Repaint();
        }
        
        private void SyncScrollPositions()
        {
            if (_leftScrollPos != _rightScrollPos)
            {
                _rightScrollPos = _leftScrollPos;
            }
        }
        
        private string GetInitialDirectory()
        {
            if (!string.IsNullOrEmpty(_baseFilePath))
                return Path.GetDirectoryName(_baseFilePath);
            return Application.dataPath;
        }
        
        #endregion
    }
    
    // // 扩展MergeStyles
    // public static partial class MergeStyles
    // {
    //     public static Texture2D MakeTexture(Color color)
    //     {
    //         var texture = new Texture2D(1, 1);
    //         texture.SetPixel(0, 0, color);
    //         texture.Apply();
    //         return texture;
    //     }
    // }
}