using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public class ArtAssetExportTool
{
    private static readonly HashSet<string> ProcessedFiles = new HashSet<string>();

    // 美术资产文件扩展名
    private static readonly HashSet<string> ArtAssetExtensions = new HashSet<string>
    {
        ".png", ".jpg", ".jpeg", ".tga", ".tiff", ".bmp", ".gif", ".psd", ".exr", ".hdr",  // 纹理
        ".fbx", ".obj", ".dae", ".3ds", ".blend", ".ma", ".mb", ".max",                    // 模型
        ".prefab",                                                                         // 预制体
        ".mat",                                                                           // 材质
        ".anim", ".controller", ".overrideController",                                    // 动画
        ".wav", ".mp3", ".ogg", ".aiff", ".flac",                                        // 音频
        ".mp4", ".mov", ".avi", ".webm",                                                  // 视频
        ".asset",                                                                         // ScriptableObject资产
        ".fontsettings", ".ttf", ".otf",                                                  // 字体
        ".physicMaterial", ".physicsMaterial2D",                                          // 物理材质
        ".terraindata",                                                                   // 地形数据
        ".cubemap",                                                                       // 立方体贴图
        ".lightingdata", ".exr",                                                          // 光照数据
        ".unity"                                                                          // 场景文件
    };

    [MenuItem("Assets/Export Art Assets Only", false, 30)]
    private static void ExportArtAssetsOnly()
    {
        ProcessedFiles.Clear();
        var selectedPaths = GetSelectedPaths();

        if (selectedPaths.Count == 0)
        {
            EditorUtility.DisplayDialog("Warning", "请先选择要导出的美术资产！", "OK");
            return;
        }

        var rootFolder = EditorUtility.SaveFolderPanel("Select Export Folder", "Assets", "");

        if (!string.IsNullOrEmpty(rootFolder))
        {
            CollectArtDependenciesRecursive(selectedPaths);
            ExportArtPackage(rootFolder);

            EditorUtility.DisplayDialog("Export Complete",
                $"成功导出 {ProcessedFiles.Count} 个美术资产文件！", "OK");
        }
    }

    private static List<string> GetSelectedPaths()
    {
        var paths = new List<string>();
        foreach (var obj in Selection.objects)
        {
            var path = AssetDatabase.GetAssetPath(obj);
            if (!IsValidAssetPath(path)) continue;

            if (System.IO.Path.HasExtension(path))
            {
                // 单个文件
                if (IsArtAsset(path))
                {
                    paths.Add(path);
                }
            }
            else
            {
                // 文件夹 - 扫描文件夹下的所有美术资产
                var folderArtAssets = GetArtAssetsInFolder(path);
                paths.AddRange(folderArtAssets);
            }
        }
        return paths.Distinct().ToList();
    }

    private static List<string> GetArtAssetsInFolder(string folderPath)
    {
        var artAssets = new List<string>();
        var fullFolderPath = Path.GetFullPath(folderPath);

        if (Directory.Exists(fullFolderPath))
        {
            var allFiles = Directory.GetFiles(fullFolderPath, "*", SearchOption.AllDirectories);

            foreach (var file in allFiles)
            {
                var relativePath = file.Replace(Application.dataPath, "Assets").Replace("\\", "/");

                if (IsArtAsset(relativePath) && IsValidAssetPath(relativePath))
                {
                    artAssets.Add(relativePath);
                }
            }
        }

        return artAssets;
    }

    private static void CollectArtDependenciesRecursive(List<string> paths)
    {
        var newPaths = new List<string>();

        foreach (var path in paths)
        {
            if (ProcessedFiles.Contains(path)) continue;

            ProcessedFiles.Add(path);
            Debug.Log($"添加美术资产: {path}");

            // 获取依赖项
            var dependencies = AssetDatabase.GetDependencies(path);
            foreach (var dep in dependencies)
            {
                if (IsArtAsset(dep) && IsValidAssetPath(dep) && !ProcessedFiles.Contains(dep))
                {
                    newPaths.Add(dep);
                }
            }
        }

        if (newPaths.Count > 0)
        {
            CollectArtDependenciesRecursive(newPaths);
        }
    }

    private static void ExportArtPackage(string folderPath)
    {
        var exportPaths = ProcessedFiles.ToArray();

        if (exportPaths.Length == 0)
        {
            EditorUtility.DisplayDialog("Warning", "没有找到可导出的美术资产！", "OK");
            return;
        }

        var packageName = $"ArtAssets_Export_{System.DateTime.Now:yyyyMMdd_HHmm}.unitypackage";
        var packagePath = Path.Combine(folderPath, packageName);

        AssetDatabase.ExportPackage(
            exportPaths,
            packagePath,
            ExportPackageOptions.Default
        );

        Debug.Log($"美术资产导出完成: {packagePath}");
        Debug.Log($"导出文件列表:");
        foreach (var path in exportPaths)
        {
            Debug.Log($"  - {path}");
        }
    }

    /// <summary>
    /// 判断是否为美术资产
    /// </summary>
    private static bool IsArtAsset(string path)
    {
        if (string.IsNullOrEmpty(path)) return false;

        var extension = Path.GetExtension(path).ToLower();

        // 检查是否在美术资产扩展名列表中
        if (ArtAssetExtensions.Contains(extension)) return true;

        // 排除代码文件
        if (IsCodeFile(path)) return false;

        // 排除Shader文件
        if (IsShaderFile(path)) return false;

        return false;
    }

    /// <summary>
    /// 判断是否为代码文件
    /// </summary>
    private static bool IsCodeFile(string path)
    {
        var extension = Path.GetExtension(path).ToLower();
        return extension == ".cs" ||
               extension == ".js" ||
               extension == ".boo" ||
               extension == ".dll";
    }

    /// <summary>
    /// 判断是否为Shader文件
    /// </summary>
    private static bool IsShaderFile(string path)
    {
        var extension = Path.GetExtension(path).ToLower();
        return extension == ".shader" ||
               extension == ".hlsl" ||
               extension == ".cginc" ||
               extension == ".glsl" ||
               extension == ".compute";
    }

    /// <summary>
    /// 判断路径是否有效
    /// </summary>
    private static bool IsValidAssetPath(string path)
    {
        return !string.IsNullOrEmpty(path) &&
               path.StartsWith("Assets") &&
               !path.Contains("Packages") &&
               !path.EndsWith(".meta");
    }

    /// <summary>
    /// 显示当前选择的美术资产信息
    /// </summary>
    [MenuItem("Assets/Show Selected Art Assets Info", false, 31)]
    private static void ShowSelectedArtAssetsInfo()
    {
        var selectedPaths = GetSelectedPaths();

        if (selectedPaths.Count == 0)
        {
            EditorUtility.DisplayDialog("Info", "当前选择中没有美术资产", "OK");
            return;
        }

        var info = $"找到 {selectedPaths.Count} 个美术资产:\n\n";
        foreach (var path in selectedPaths.Take(20)) // 最多显示20个
        {
            info += $"• {path}\n";
        }

        if (selectedPaths.Count > 20)
        {
            info += $"... 还有 {selectedPaths.Count - 20} 个文件";
        }

        EditorUtility.DisplayDialog("Selected Art Assets", info, "OK");
    }
}