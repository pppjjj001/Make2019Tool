// using UnityEngine;
// using UnityEditor;
// using System.Collections.Generic;
// using System.IO;
// using System.Text.RegularExpressions;
//
// public class ResourceDependencyTool
// {
//     private static HashSet<string> _collectedAssets = new HashSet<string>();
//     private static readonly string PackagePrefix = "Packages/";
//     private static readonly string CsExtension = ".cs";
//
//     [MenuItem("Assets/Advanced Package Export")]
//     private static void StartExportProcess()
//     {
//         _collectedAssets.Clear();
//         
//         // 初始选择资源收集
//         foreach (var guid in Selection.assetGUIDs)
//         {
//             string path = AssetDatabase.GUIDToAssetPath(guid);
//             if (ShouldProcessPath(path))
//             {
//                 CollectDependenciesRecursive(path);
//             }
//         }
//
//         // 处理Shader引用
//         ProcessShaderReferences();
//
//         // 处理HLSL递归引用
//         ProcessHLSLRecursive();
//
//         // 打包输出
//         string outputPath = EditorUtility.SaveFolderPanel("Select Export Directory", "", "");
//         if (!string.IsNullOrEmpty(outputPath))
//         {
//             ExportFinalPackage(outputPath);
//         }
//     }
//
//     private static bool ShouldProcessPath(string path)
//     {
//         return !path.StartsWith(PackagePrefix) && 
//                !path.EndsWith(CsExtension) &&
//                !_collectedAssets.Contains(path);
//     }
//
//     private static void CollectDependenciesRecursive(string path)
//     {
//         if (!AssetDatabase.IsValidFolder(path))
//         {
//             foreach (var dependency in AssetDatabase.GetDependencies(path, false))
//             {
//                 if (ShouldProcessPath(dependency))
//                 {
//                     _collectedAssets.Add(dependency);
//                     CollectDependenciesRecursive(dependency);
//                 }
//             }
//         }
//     }
//
//     private static void ProcessShaderReferences()
//     {
//         var shaders = new List<string>();
//         foreach (var asset in _collectedAssets)
//         {
//             if (asset.EndsWith(".shader"))
//             {
//                 shaders.Add(asset);
//             }
//         }
//
//         foreach (var shaderPath in shaders)
//         {
//             ParseShaderIncludes(shaderPath);
//         }
//     }
//
//     private static void ParseShaderIncludes(string shaderPath)
//     {
//         string fullPath = Path.Combine(Application.dataPath.Replace("Assets", ""), shaderPath);
//         string[] lines = File.ReadAllLines(fullPath);
//
//         foreach (var line in lines)
//         {
//             var match = Regex.Match(line, @"#include\s+""([^""]+\.hlsl)""");
//             if (match.Success)
//             {
//                 string hlslPath = Path.Combine(Path.GetDirectoryName(shaderPath), match.Groups[1].Value);
//                 hlslPath = hlslPath.Replace("\\", "/");
//
//                 if (ShouldProcessPath(hlslPath) && File.Exists(Path.Combine(Application.dataPath, hlslPath)))
//                 {
//                     _collectedAssets.Add(hlslPath);
//                 }
//             }
//         }
//     }
//
//     private static void ProcessHLSLRecursive()
//     {
//         bool foundNew;
//         do
//         {
//             foundNew = false;
//             var currentHLSL = new List<string>(_collectedAssets);
//             
//             foreach (var hlslPath in currentHLSL)
//             {
//                 if (hlslPath.EndsWith(".hlsl"))
//                 {
//                     string fullPath = Path.Combine(Application.dataPath.Replace("Assets", ""), hlslPath);
//                     string[] lines = File.ReadAllLines(fullPath);
//
//                     foreach (var line in lines)
//                     {
//                         var match = Regex.Match(line, @"#include\s+""([^""]+\.hlsl)""");
//                         if (match.Success)
//                         {
//                             string newHlslPath = Path.Combine(Path.GetDirectoryName(hlslPath), match.Groups[1].Value);
//                             newHlslPath = newHlslPath.Replace("\\", "/");
//
//                             if (ShouldProcessPath(newHlslPath) && File.Exists(Path.Combine(Application.dataPath, newHlslPath)))
//                             {
//                                 foundNew = true;
//                                 _collectedAssets.Add(newHlslPath);
//                             }
//                         }
//                     }
//                 }
//             }
//         } while (foundNew);
//     }
//
//     private static void ExportFinalPackage(string outputFolder)
//     {
//         List<string> exportPaths = new List<string>();
//         foreach (var asset in _collectedAssets)
//         {
//             exportPaths.Add(asset);
//         }
//
//         string packageName = $"CustomExport_{System.DateTime.Now:yyyyMMdd_HHmm}.unitypackage";
//         string fullPath = Path.Combine(outputFolder, packageName);
//         
//         AssetDatabase.ExportPackage(
//             exportPaths.ToArray(), 
//             fullPath, 
//             ExportPackageOptions.Interactive | ExportPackageOptions.Recurse
//         );
//     }
// }

using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

public class ResourceDependencyTool
{
    private static readonly HashSet<string> ProcessedFiles = new HashSet<string>();
    private static readonly List<string> PackagePaths = new List<string> { "Packages" };
    [MenuItem("Assets/Custom Package Export", false, 30)]
    private static void ExportCustomPackage()
    {
        ProcessedFiles.Clear();
        var selectedPaths = GetSelectedPaths();
        var rootFolder = EditorUtility.SaveFolderPanel("Select Export Folder", "Assets", "");

        if (!string.IsNullOrEmpty(rootFolder))
        {
            CollectDependenciesRecursive(selectedPaths);
            ExportFinalPackage(rootFolder);
        }
    }
    static List<string> GetFilesInFolder(string folderPath)
    {
        List<string> files = new List<string>();

        if (Directory.Exists(folderPath))
        {
            string[] currentFiles = Directory.GetFiles(folderPath);
            
            files.AddRange(currentFiles);

            // 递归获取子文件夹下的所有文件
            string[] subFolders = Directory.GetDirectories(folderPath);
            foreach (string subFolder in subFolders)
            {
                files.AddRange(GetFilesInFolder(subFolder));
            }
        }
        else
        {
            Debug.LogWarning("文件夹路径不存在：" + folderPath);
        }

        return files;
    }
    private static List<string> GetSelectedPaths()
    {
        var paths = new List<string>();
        foreach (var obj in Selection.objects)
        {
            var path = AssetDatabase.GetAssetPath(obj);
            Debug.Log(path);
            if (!IsValidPath(path)) continue;
            if (System.IO.Path.HasExtension(path))
            {
                paths.Add(path);
            }
            else
            {
                //如果是文件夹 扫面文件夹下的所有资源
                string useFilePath = Application.dataPath + path.Substring(6);

                List<string> filePaths = GetFilesInFolder(useFilePath);
                if (filePaths.Count > 0)
                {
                    for (int i = 0; i < filePaths.Count; i++)
                    {
                        filePaths[i] = filePaths[i].Replace(Application.dataPath, "Assets");
                    }
                    paths.AddRange(filePaths);
                }
            }
        }
        return paths;
    }

    private static void CollectDependenciesRecursive(List<string> paths)
    {
        var newPaths = new List<string>();
        
        foreach (var path in paths)
        {
            if (ProcessedFiles.Contains(path)) continue;
                ProcessedFiles.Add(path);
            if (IsShaderFile(path)) ProcessShaderIncludes(path);
            
            var dependencies = AssetDatabase.GetDependencies(path);
            foreach (var dep in dependencies)
            {
                if (IsValidPath(dep) && !ProcessedFiles.Contains(dep))
                    newPaths.Add(dep);
            }
        }

        if (newPaths.Count > 0) CollectDependenciesRecursive(newPaths);
    }

    private static void ProcessShaderIncludes(string shaderPath)
    {
        var shaderContent = File.ReadAllText(shaderPath);
        var matches = Regex.Matches(shaderContent, @"#include\s+[""'](.+?)[""']");

        foreach (Match match in matches)
        {
            var includePath = match.Groups[1].Value;
            Debug.Log("ProcessShaderIncludes "+includePath);
            var fullPath = ResolveIncludePath(shaderPath, includePath);
            
            Debug.Log("ResolveIncludePath "+fullPath);
            if (File.Exists(fullPath) && IsValidUse(fullPath) && !ProcessedFiles.Contains(fullPath))
            {
                Debug.Log("ProcessedFiles.Add "+fullPath);
                ProcessedFiles.Add(fullPath);
                ProcessShaderIncludes(fullPath);
            }
        }
    }

    private static string ResolveIncludePath(string basePath, string includePath)
    {
        var directory = System.IO.Path.GetDirectoryName(basePath);
        directory = directory.Replace("\\", "/");
        if (includePath.StartsWith("\"") || includePath.StartsWith("'"))
            includePath = includePath.Substring(1, includePath.Length - 2);

        if (includePath.StartsWith("...") || !includePath.Contains("/"))
        {
            Debug.Log(" ...Combine directory "+directory);
            return Path.Combine(directory, includePath.TrimStart('/'));
        }

        return Path.Combine(Application.dataPath.Replace("Assets", ""), includePath);
    }

    private static void ExportFinalPackage(string folderPath)
    {
        var exportPaths = new List<string>();
        foreach (var path in ProcessedFiles)
        {
            Debug.Log("ExportFinalPackage " + path);
            exportPaths.Add(path.Replace(Application.dataPath, "Assets"));
        }

        AssetDatabase.ExportPackage(
            exportPaths.ToArray(),
            $"{folderPath}/CustomExport_{System.DateTime.Now:yyyyMMdd_HHmm}.unitypackage",
            ExportPackageOptions.Default
        );
    }

    private static bool IsValidUse(string path)
    {
        return !path.EndsWith(".cs") &&
               !path.Contains("Packages");
    }
    private static bool IsValidPath(string path)
    {
        return !path.EndsWith(".cs") && 
               !path.Contains("Packages") &&
               path.StartsWith("Assets");
    }

    private static bool IsShaderFile(string path)
    {
        return path.EndsWith(".shader") || 
               path.EndsWith(".hlsl") || 
               path.EndsWith(".cginc");
    }
}
