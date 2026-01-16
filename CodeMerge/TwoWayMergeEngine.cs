using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace CodeMerge
{
    /// <summary>
    /// 双向合并块
    /// </summary>
    public class TwoWayMergeBlock
    {
        public DiffType Type;
        public List<string> BaseLines = new List<string>();
        public List<string> LocalLines = new List<string>();
        public List<string> MergedLines = new List<string>();
        public int BaseStartLine;
        public int LocalStartLine;
        public bool UseLocal = true;  // 默认使用Local的改动
        
        public bool HasDifference => Type != DiffType.Equal;
    }

    /// <summary>
    /// 双向合并结果
    /// </summary>
    public class TwoWayMergeResult
    {
        public List<TwoWayMergeBlock> Blocks = new List<TwoWayMergeBlock>();
        public List<NameReplacement> NameReplacements = new List<NameReplacement>();
        
        public int DifferenceCount => Blocks.Count(b => b.HasDifference);
        
        public string GetMergedContent()
        {
            var sb = new StringBuilder();
            foreach (var block in Blocks)
            {
                var lines = block.MergedLines.Count > 0 ? block.MergedLines :
                    (block.UseLocal ? block.LocalLines : block.BaseLines);
                
                foreach (var line in lines)
                {
                    sb.AppendLine(line);
                }
            }
            return sb.ToString().TrimEnd('\r', '\n');
        }
        
        /// <summary>
        /// 重新计算合并内容
        /// </summary>
        public void RecalculateMerged()
        {
            foreach (var block in Blocks)
            {
                block.MergedLines.Clear();
                if (block.Type == DiffType.Equal)
                {
                    block.MergedLines.AddRange(block.BaseLines);
                }
                else
                {
                    block.MergedLines.AddRange(block.UseLocal ? block.LocalLines : block.BaseLines);
                }
            }
        }
    }

    /// <summary>
    /// 双向合并引擎
    /// </summary>
    public static class TwoWayMergeEngine
    {
        /// <summary>
        /// 执行双向合并
        /// </summary>
        public static TwoWayMergeResult Merge(
            string baseContent, 
            string localContent,
            PreserveOptions preserveOptions = PreserveOptions.None)
        {
            var result = new TwoWayMergeResult();
            
            // 如果需要保留类名，先进行名称替换
            string processedLocal = localContent;
            if (preserveOptions != PreserveOptions.None)
            {
                processedLocal = ClassNamePreserver.ApplyNamePreservation(
                    baseContent, 
                    localContent, 
                    preserveOptions,
                    out var replacements);
                
                result.NameReplacements = replacements;
            }
            
            // 分割为行
            var baseLines = SplitLines(baseContent);
            var localLines = SplitLines(processedLocal);
            
            // 计算差异
            var diffs = DiffAlgorithm.ComputeDiff(baseLines, localLines);
            diffs = DiffAlgorithm.MergeConsecutiveBlocks(diffs);
            
            // 构建合并块
            int baseLineNo = 0;
            int localLineNo = 0;
            
            foreach (var diff in diffs)
            {
                var block = new TwoWayMergeBlock
                {
                    Type = diff.Type,
                    BaseStartLine = baseLineNo,
                    LocalStartLine = localLineNo
                };
                
                block.BaseLines.AddRange(diff.BaseLines);
                block.LocalLines.AddRange(diff.NewLines);
                
                // 默认合并策略
                if (diff.Type == DiffType.Equal)
                {
                    block.MergedLines.AddRange(diff.BaseLines);
                    block.UseLocal = false;
                }
                else
                {
                    // 使用Local的改动
                    block.MergedLines.AddRange(diff.NewLines);
                    block.UseLocal = true;
                }
                
                baseLineNo += diff.BaseLines.Count;
                localLineNo += diff.NewLines.Count;
                
                result.Blocks.Add(block);
            }
            
            return result;
        }

        /// <summary>
        /// 智能合并 - 尝试自动选择最佳合并策略
        /// </summary>
        public static TwoWayMergeResult SmartMerge(
            string baseContent,
            string localContent,
            PreserveOptions preserveOptions = PreserveOptions.None)
        {
            var result = Merge(baseContent, localContent, preserveOptions);
            
            // 应用智能合并策略
            foreach (var block in result.Blocks)
            {
                if (block.Type == DiffType.Equal) continue;
                
                // 策略1: 如果Local只是添加内容，保留添加
                if (block.Type == DiffType.Added)
                {
                    block.UseLocal = true;
                    continue;
                }
                
                // 策略2: 如果Local只是删除内容，检查是否应该保留删除
                if (block.Type == DiffType.Removed)
                {
                    // 默认保留删除（使用Local的空内容）
                    block.UseLocal = true;
                    continue;
                }
                
                // 策略3: 修改的情况，默认使用Local
                block.UseLocal = true;
            }
            
            result.RecalculateMerged();
            return result;
        }

        /// <summary>
        /// 预览名称改动
        /// </summary>
        public static Dictionary<string, string> PreviewNameChanges(string baseContent, string localContent)
        {
            return ClassNamePreserver.DetectNameMappings(baseContent, localContent);
        }

        private static string[] SplitLines(string content)
        {
            if (string.IsNullOrEmpty(content))
                return Array.Empty<string>();
            
            return content.Replace("\r\n", "\n").Replace("\r", "\n").Split('\n');
        }
    }
}
