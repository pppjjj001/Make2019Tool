using System;
using System.Collections.Generic;
using System.Linq;

namespace CodeMerge
{
    public enum DiffType
    {
        Equal,      // 相同
        Added,      // 新增
        Removed,    // 删除
        Modified    // 修改
    }

    public class DiffBlock
    {
        public DiffType Type;
        public List<string> BaseLines = new List<string>();
        public List<string> NewLines = new List<string>();
        public int BaseStartLine;
        public int NewStartLine;
        
        public override string ToString()
        {
            return $"[{Type}] Base:{BaseStartLine} New:{NewStartLine} Lines:{BaseLines.Count}/{NewLines.Count}";
        }
    }

    public class DiffAlgorithm
    {
        /// <summary>
        /// 计算两个文本的差异（基于LCS算法）
        /// </summary>
        public static List<DiffBlock> ComputeDiff(string[] baseLines, string[] newLines)
        {
            var lcs = ComputeLCS(baseLines, newLines);
            return BuildDiffBlocks(baseLines, newLines, lcs);
        }

        /// <summary>
        /// 计算最长公共子序列
        /// </summary>
        private static List<(int baseIdx, int newIdx)> ComputeLCS(string[] baseLines, string[] newLines)
        {
            int m = baseLines.Length;
            int n = newLines.Length;
            
            // DP表
            int[,] dp = new int[m + 1, n + 1];
            
            // 填充DP表
            for (int i = 1; i <= m; i++)
            {
                for (int j = 1; j <= n; j++)
                {
                    if (baseLines[i - 1] == newLines[j - 1])
                    {
                        dp[i, j] = dp[i - 1, j - 1] + 1;
                    }
                    else
                    {
                        dp[i, j] = Math.Max(dp[i - 1, j], dp[i, j - 1]);
                    }
                }
            }
            
            // 回溯获取LCS
            var lcs = new List<(int baseIdx, int newIdx)>();
            int x = m, y = n;
            
            while (x > 0 && y > 0)
            {
                if (baseLines[x - 1] == newLines[y - 1])
                {
                    lcs.Add((x - 1, y - 1));
                    x--;
                    y--;
                }
                else if (dp[x - 1, y] > dp[x, y - 1])
                {
                    x--;
                }
                else
                {
                    y--;
                }
            }
            
            lcs.Reverse();
            return lcs;
        }

        /// <summary>
        /// 根据LCS构建差异块
        /// </summary>
        private static List<DiffBlock> BuildDiffBlocks(string[] baseLines, string[] newLines, 
            List<(int baseIdx, int newIdx)> lcs)
        {
            var blocks = new List<DiffBlock>();
            int baseIdx = 0;
            int newIdx = 0;
            
            foreach (var (lcsBaseIdx, lcsNewIdx) in lcs)
            {
                // 处理LCS匹配点之前的差异
                if (baseIdx < lcsBaseIdx || newIdx < lcsNewIdx)
                {
                    var diffBlock = new DiffBlock
                    {
                        BaseStartLine = baseIdx,
                        NewStartLine = newIdx
                    };
                    
                    // 收集删除的行
                    while (baseIdx < lcsBaseIdx)
                    {
                        diffBlock.BaseLines.Add(baseLines[baseIdx++]);
                    }
                    
                    // 收集新增的行
                    while (newIdx < lcsNewIdx)
                    {
                        diffBlock.NewLines.Add(newLines[newIdx++]);
                    }
                    
                    // 确定差异类型
                    if (diffBlock.BaseLines.Count > 0 && diffBlock.NewLines.Count > 0)
                        diffBlock.Type = DiffType.Modified;
                    else if (diffBlock.BaseLines.Count > 0)
                        diffBlock.Type = DiffType.Removed;
                    else
                        diffBlock.Type = DiffType.Added;
                    
                    blocks.Add(diffBlock);
                }
                
                // 添加相同的行
                blocks.Add(new DiffBlock
                {
                    Type = DiffType.Equal,
                    BaseLines = new List<string> { baseLines[lcsBaseIdx] },
                    NewLines = new List<string> { newLines[lcsNewIdx] },
                    BaseStartLine = baseIdx,
                    NewStartLine = newIdx
                });
                
                baseIdx = lcsBaseIdx + 1;
                newIdx = lcsNewIdx + 1;
            }
            
            // 处理剩余的行
            if (baseIdx < baseLines.Length || newIdx < newLines.Length)
            {
                var diffBlock = new DiffBlock
                {
                    BaseStartLine = baseIdx,
                    NewStartLine = newIdx
                };
                
                while (baseIdx < baseLines.Length)
                {
                    diffBlock.BaseLines.Add(baseLines[baseIdx++]);
                }
                
                while (newIdx < newLines.Length)
                {
                    diffBlock.NewLines.Add(newLines[newIdx++]);
                }
                
                if (diffBlock.BaseLines.Count > 0 && diffBlock.NewLines.Count > 0)
                    diffBlock.Type = DiffType.Modified;
                else if (diffBlock.BaseLines.Count > 0)
                    diffBlock.Type = DiffType.Removed;
                else
                    diffBlock.Type = DiffType.Added;
                
                blocks.Add(diffBlock);
            }
            
            return blocks;
        }

        /// <summary>
        /// 合并连续的相同类型块
        /// </summary>
        public static List<DiffBlock> MergeConsecutiveBlocks(List<DiffBlock> blocks)
        {
            if (blocks.Count == 0) return blocks;
            
            var merged = new List<DiffBlock>();
            DiffBlock current = null;
            
            foreach (var block in blocks)
            {
                if (current == null)
                {
                    current = CloneBlock(block);
                }
                else if (current.Type == block.Type && current.Type == DiffType.Equal)
                {
                    current.BaseLines.AddRange(block.BaseLines);
                    current.NewLines.AddRange(block.NewLines);
                }
                else
                {
                    merged.Add(current);
                    current = CloneBlock(block);
                }
            }
            
            if (current != null)
                merged.Add(current);
            
            return merged;
        }

        private static DiffBlock CloneBlock(DiffBlock block)
        {
            return new DiffBlock
            {
                Type = block.Type,
                BaseLines = new List<string>(block.BaseLines),
                NewLines = new List<string>(block.NewLines),
                BaseStartLine = block.BaseStartLine,
                NewStartLine = block.NewStartLine
            };
        }
    }
}