using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace CodeMerge
{
    public enum ConflictResolution
    {
        TakeBase,
        TakeLocal,
        TakeRemote,
        TakeBoth,
        Manual
    }

    public class MergeBlock
    {
        public bool IsConflict;
        public List<string> BaseContent = new List<string>();
        public List<string> LocalContent = new List<string>();
        public List<string> RemoteContent = new List<string>();
        public List<string> MergedContent = new List<string>();
        public ConflictResolution Resolution = ConflictResolution.Manual;
        public int StartLine;
        
        public bool IsResolved => !IsConflict || Resolution != ConflictResolution.Manual;
    }

    public class MergeResult
    {
        public List<MergeBlock> Blocks = new List<MergeBlock>();
        public bool HasConflicts => Blocks.Any(b => b.IsConflict && !b.IsResolved);
        public int ConflictCount => Blocks.Count(b => b.IsConflict);
        public int UnresolvedCount => Blocks.Count(b => b.IsConflict && !b.IsResolved);
        
        public string GetMergedContent()
        {
            var sb = new StringBuilder();
            foreach (var block in Blocks)
            {
                var content = block.IsResolved ? block.MergedContent : 
                    (block.IsConflict ? GetConflictMarker(block) : block.MergedContent);
                
                foreach (var line in content)
                {
                    sb.AppendLine(line);
                }
            }
            return sb.ToString().TrimEnd('\r', '\n');
        }

        private List<string> GetConflictMarker(MergeBlock block)
        {
            var lines = new List<string>();
            lines.Add("<<<<<<< LOCAL");
            lines.AddRange(block.LocalContent);
            lines.Add("=======");
            lines.AddRange(block.RemoteContent);
            lines.Add(">>>>>>> REMOTE");
            return lines;
        }
    }

    public class MergeEngine
    {
        /// <summary>
        /// 三方合并
        /// </summary>
        /// <param name="baseContent">基准版本（共同祖先）</param>
        /// <param name="localContent">本地版本</param>
        /// <param name="remoteContent">远程版本</param>
        public static MergeResult ThreeWayMerge(string baseContent, string localContent, string remoteContent)
        {
            var baseLines = SplitLines(baseContent);
            var localLines = SplitLines(localContent);
            var remoteLines = SplitLines(remoteContent);
            
            return ThreeWayMerge(baseLines, localLines, remoteLines);
        }

        public static MergeResult ThreeWayMerge(string[] baseLines, string[] localLines, string[] remoteLines)
        {
            var result = new MergeResult();
            
            // 计算本地和远程相对于基准的差异
            var localDiff = DiffAlgorithm.ComputeDiff(baseLines, localLines);
            var remoteDiff = DiffAlgorithm.ComputeDiff(baseLines, remoteLines);
            
            localDiff = DiffAlgorithm.MergeConsecutiveBlocks(localDiff);
            remoteDiff = DiffAlgorithm.MergeConsecutiveBlocks(remoteDiff);
            
            // 构建变更映射
            var localChanges = BuildChangeMap(localDiff);
            var remoteChanges = BuildChangeMap(remoteDiff);
            
            // 合并处理
            int baseIdx = 0;
            var processedRanges = new HashSet<int>();
            
            // 获取所有变更区域并排序
            var allChangeStarts = localChanges.Keys.Concat(remoteChanges.Keys)
                .Distinct()
                .OrderBy(x => x)
                .ToList();
            
            foreach (var changeStart in allChangeStarts)
            {
                // 添加变更之前的未变更内容
                if (baseIdx < changeStart)
                {
                    var unchangedBlock = new MergeBlock
                    {
                        IsConflict = false,
                        StartLine = baseIdx
                    };
                    
                    for (int i = baseIdx; i < changeStart && i < baseLines.Length; i++)
                    {
                        unchangedBlock.MergedContent.Add(baseLines[i]);
                        unchangedBlock.BaseContent.Add(baseLines[i]);
                    }
                    
                    if (unchangedBlock.MergedContent.Count > 0)
                        result.Blocks.Add(unchangedBlock);
                    
                    baseIdx = changeStart;
                }
                
                if (processedRanges.Contains(changeStart))
                    continue;
                
                localChanges.TryGetValue(changeStart, out var localBlock);
                remoteChanges.TryGetValue(changeStart, out var remoteBlock);
                
                var mergeBlock = new MergeBlock
                {
                    StartLine = changeStart
                };
                
                // 设置基准内容
                if (localBlock != null)
                    mergeBlock.BaseContent.AddRange(localBlock.BaseLines);
                else if (remoteBlock != null)
                    mergeBlock.BaseContent.AddRange(remoteBlock.BaseLines);
                
                // 分析变更情况
                bool localChanged = localBlock != null && localBlock.Type != DiffType.Equal;
                bool remoteChanged = remoteBlock != null && remoteBlock.Type != DiffType.Equal;
                
                if (localChanged && remoteChanged)
                {
                    // 双方都有变更
                    mergeBlock.LocalContent.AddRange(localBlock.NewLines);
                    mergeBlock.RemoteContent.AddRange(remoteBlock.NewLines);
                    
                    // 检查是否相同变更（无冲突）
                    if (AreEqual(localBlock.NewLines, remoteBlock.NewLines))
                    {
                        mergeBlock.IsConflict = false;
                        mergeBlock.MergedContent.AddRange(localBlock.NewLines);
                    }
                    else
                    {
                        // 尝试智能合并
                        if (TrySmartMerge(localBlock, remoteBlock, out var smartMerged))
                        {
                            mergeBlock.IsConflict = false;
                            mergeBlock.MergedContent.AddRange(smartMerged);
                        }
                        else
                        {
                            mergeBlock.IsConflict = true;
                        }
                    }
                    
                    baseIdx = changeStart + Math.Max(localBlock.BaseLines.Count, remoteBlock.BaseLines.Count);
                }
                else if (localChanged)
                {
                    // 只有本地变更
                    mergeBlock.IsConflict = false;
                    mergeBlock.LocalContent.AddRange(localBlock.NewLines);
                    mergeBlock.RemoteContent.AddRange(localBlock.BaseLines);
                    mergeBlock.MergedContent.AddRange(localBlock.NewLines);
                    baseIdx = changeStart + localBlock.BaseLines.Count;
                }
                else if (remoteChanged)
                {
                    // 只有远程变更
                    mergeBlock.IsConflict = false;
                    mergeBlock.LocalContent.AddRange(remoteBlock.BaseLines);
                    mergeBlock.RemoteContent.AddRange(remoteBlock.NewLines);
                    mergeBlock.MergedContent.AddRange(remoteBlock.NewLines);
                    baseIdx = changeStart + remoteBlock.BaseLines.Count;
                }
                
                processedRanges.Add(changeStart);
                result.Blocks.Add(mergeBlock);
            }
            
            // 添加剩余的未变更内容
            if (baseIdx < baseLines.Length)
            {
                var remainingBlock = new MergeBlock
                {
                    IsConflict = false,
                    StartLine = baseIdx
                };
                
                for (int i = baseIdx; i < baseLines.Length; i++)
                {
                    remainingBlock.MergedContent.Add(baseLines[i]);
                    remainingBlock.BaseContent.Add(baseLines[i]);
                }
                
                result.Blocks.Add(remainingBlock);
            }
            
            return result;
        }

        /// <summary>
        /// 构建变更映射（基准行号 -> 差异块）
        /// </summary>
        private static Dictionary<int, DiffBlock> BuildChangeMap(List<DiffBlock> diffs)
        {
            var map = new Dictionary<int, DiffBlock>();
            int baseLineNo = 0;
            
            foreach (var diff in diffs)
            {
                if (diff.Type != DiffType.Equal)
                {
                    map[baseLineNo] = diff;
                }
                baseLineNo += diff.BaseLines.Count;
            }
            
            return map;
        }

        /// <summary>
        /// 尝试智能合并（处理不冲突的相邻变更）
        /// </summary>
        private static bool TrySmartMerge(DiffBlock local, DiffBlock remote, out List<string> merged)
        {
            merged = new List<string>();
            
            // 如果一方是纯添加，另一方是修改，可能可以合并
            if (local.BaseLines.Count == 0 && remote.BaseLines.Count == 0)
            {
                // 两边都是纯添加到同一位置，需要检查是否可以合并
                // 简单策略：本地在前，远程在后
                merged.AddRange(local.NewLines);
                merged.AddRange(remote.NewLines);
                return true;
            }
            
            // 检查是否是对不同部分的修改
            if (TryMergeNonOverlapping(local, remote, out merged))
            {
                return true;
            }
            
            return false;
        }

        /// <summary>
        /// 尝试合并非重叠的变更
        /// </summary>
        private static bool TryMergeNonOverlapping(DiffBlock local, DiffBlock remote, out List<string> merged)
        {
            merged = new List<string>();
            
            // 使用行级别的细粒度合并
            var baseLines = local.BaseLines.Count > 0 ? local.BaseLines : remote.BaseLines;
            var localNew = local.NewLines;
            var remoteNew = remote.NewLines;
            
            // 找出本地和远程分别修改了哪些行
            var localDiff = DiffAlgorithm.ComputeDiff(baseLines.ToArray(), localNew.ToArray());
            var remoteDiff = DiffAlgorithm.ComputeDiff(baseLines.ToArray(), remoteNew.ToArray());
            
            // 检查是否有重叠
            var localChangedLines = GetChangedLineIndices(localDiff);
            var remoteChangedLines = GetChangedLineIndices(remoteDiff);
            
            if (localChangedLines.Intersect(remoteChangedLines).Any())
            {
                // 有重叠，无法自动合并
                return false;
            }
            
            // 应用双方的变更
            // 这里简化处理，实际需要更复杂的合并逻辑
            return false;
        }

        private static HashSet<int> GetChangedLineIndices(List<DiffBlock> diffs)
        {
            var indices = new HashSet<int>();
            int lineNo = 0;
            
            foreach (var diff in diffs)
            {
                if (diff.Type != DiffType.Equal)
                {
                    for (int i = 0; i < diff.BaseLines.Count; i++)
                    {
                        indices.Add(lineNo + i);
                    }
                }
                lineNo += diff.BaseLines.Count;
            }
            
            return indices;
        }

        private static bool AreEqual(List<string> a, List<string> b)
        {
            if (a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++)
            {
                if (a[i] != b[i]) return false;
            }
            return true;
        }

        private static string[] SplitLines(string content)
        {
            if (string.IsNullOrEmpty(content))
                return Array.Empty<string>();
            
            return content.Replace("\r\n", "\n").Replace("\r", "\n").Split('\n');
        }

        /// <summary>
        /// 解决冲突
        /// </summary>
        public static void ResolveConflict(MergeBlock block, ConflictResolution resolution, 
            string[] customContent = null)
        {
            block.Resolution = resolution;
            block.MergedContent.Clear();
            
            switch (resolution)
            {
                case ConflictResolution.TakeBase:
                    block.MergedContent.AddRange(block.BaseContent);
                    break;
                case ConflictResolution.TakeLocal:
                    block.MergedContent.AddRange(block.LocalContent);
                    break;
                case ConflictResolution.TakeRemote:
                    block.MergedContent.AddRange(block.RemoteContent);
                    break;
                case ConflictResolution.TakeBoth:
                    block.MergedContent.AddRange(block.LocalContent);
                    block.MergedContent.AddRange(block.RemoteContent);
                    break;
                case ConflictResolution.Manual:
                    if (customContent != null)
                        block.MergedContent.AddRange(customContent);
                    break;
            }
        }
    }
}
