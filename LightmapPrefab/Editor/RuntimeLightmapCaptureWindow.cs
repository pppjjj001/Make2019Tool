// using UnityEngine;
// using UnityEditor;
// using UnityEngine.SceneManagement;
// using System.Collections.Generic;
// using System.IO;
//
// public class RuntimeLightmapCaptureWindow : EditorWindow
// {
//     private RuntimeLightmapData currentData;
//     private Vector2 scrollPosition;
//     private bool showCaptureSettings = true;
//     private bool showObjectList = false;
//
//     [MenuItem("Window/Lighting/Runtime Lightmap Capture")]
//     public static void ShowWindow()
//     {
//         GetWindow<RuntimeLightmapCaptureWindow>("Runtime Lightmap Capture");
//     }
//
//     private void OnGUI()
//     {
//         scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);
//
//         EditorGUILayout.LabelField("Runtime Lightmap Capture Tool", EditorStyles.boldLabel);
//         EditorGUILayout.Space();
//
//         // 数据资源选择
//         EditorGUILayout.BeginHorizontal();
//         currentData = EditorGUILayout.ObjectField("Runtime Lightmap Data",
//             currentData, typeof(RuntimeLightmapData), false) as RuntimeLightmapData;
//
//         if (GUILayout.Button("Create New", GUILayout.Width(100)))
//         {
//             CreateNewRuntimeLightmapData();
//         }
//         EditorGUILayout.EndHorizontal();
//
//         if (currentData == null)
//         {
//             EditorGUILayout.HelpBox("Please select or create a Runtime Lightmap Data asset to continue.",
//                 MessageType.Info);
//             EditorGUILayout.EndScrollView();
//             return;
//         }
//
//         EditorGUILayout.Space();
//
//         // 捕获设置
//         showCaptureSettings = EditorGUILayout.Foldout(showCaptureSettings, "Capture Settings");
//         if (showCaptureSettings)
//         {
//             EditorGUI.indentLevel++;
//             currentData.enableLightmap = EditorGUILayout.Toggle("Enable Lightmap", currentData.enableLightmap);
//             currentData.enableDirectionalLightmap = EditorGUILayout.Toggle("Enable Directional Lightmap", currentData.enableDirectionalLightmap);
//             currentData.enableShadowMask = EditorGUILayout.Toggle("Enable Shadow Mask", currentData.enableShadowMask);
//             EditorGUI.indentLevel--;
//         }
//
//         EditorGUILayout.Space();
//
//         // 主要操作按钮
//         if (GUILayout.Button("Capture Scene Lightmap Data", GUILayout.Height(30)))
//         {
//             CaptureSceneLightmapData();
//         }
//
//         if (GUILayout.Button("Create Runtime Applier in Scene", GUILayout.Height(25)))
//         {
//             CreateRuntimeApplierInScene();
//         }
//
//         EditorGUILayout.Space();
//
//         // 显示捕获的数据信息
//         DisplayCapturedDataInfo();
//
//         EditorGUILayout.EndScrollView();
//     }
//
//     private void CreateNewRuntimeLightmapData()
//     {
//         string sceneName = SceneManager.GetActiveScene().name;
//         string path = EditorUtility.SaveFilePanelInProject(
//             "Create Runtime Lightmap Data",
//             $"RuntimeLightmapData_{sceneName}",
//             "asset",
//             "Choose location to save runtime lightmap data");
//
//         if (!string.IsNullOrEmpty(path))
//         {
//             RuntimeLightmapData newData = CreateInstance<RuntimeLightmapData>();
//             newData.sceneName = sceneName;
//             newData.sceneGUID = AssetDatabase.AssetPathToGUID(SceneManager.GetActiveScene().path);
//
//             AssetDatabase.CreateAsset(newData, path);
//             AssetDatabase.SaveAssets();
//
//             currentData = newData;
//             Selection.activeObject = newData;
//         }
//     }
//
//     private void CaptureSceneLightmapData()
//     {
//         if (currentData == null)
//         {
//             Debug.LogError("No runtime lightmap data asset selected!");
//             return;
//         }
//
//         // 清除现有数据
//         currentData.objectData.Clear();
//         currentData.lightmapTextures.Clear();
//
//         // 更新场景信息
//         Scene activeScene = SceneManager.GetActiveScene();
//         currentData.sceneName = activeScene.name;
//         currentData.sceneGUID = AssetDatabase.AssetPathToGUID(activeScene.path);
//
//         // 捕获环境光设置
//         currentData.ambientColor = RenderSettings.ambientLight;
//         currentData.ambientIntensity = RenderSettings.ambientIntensity;
//
//         // 捕获lightmap纹理
//         CaptureLightmapTextures();
//
//         // 捕获对象数据
//         CaptureObjectLightmapData();
//
//         EditorUtility.SetDirty(currentData);
//         AssetDatabase.SaveAssets();
//
//         Debug.Log($"Captured lightmap data: {currentData.objectData.Count} objects, {currentData.lightmapTextures.Count} lightmaps");
//     }
//
//     private void CaptureLightmapTextures()
//     {
//         var lightmaps = LightmapSettings.lightmaps;
//
//         for (int i = 0; i < lightmaps.Length; i++)
//         {
//             LightmapTextureSet textureSet = new LightmapTextureSet
//             {
//                 lightmapColor = lightmaps[i].lightmapColor,
//                 lightmapDir = lightmaps[i].lightmapDir,
//                 shadowMask = lightmaps[i].shadowMask
//             };
//
//             currentData.lightmapTextures.Add(textureSet);
//         }
//     }
//     private bool CheckGPUInstancingStatus(Material material)
//     {
//         if (material == null) return false;
//     
//         // 检查材质是否启用GPU Instancing
//         bool materialEnabled = material.enableInstancing;
//     
//         // 检查Shader是否支持GPU Instancing
//         bool shaderSupported = material.shader != null &&
//                                material.shader.isSupported;
//     
//         return materialEnabled && shaderSupported;
//     }
//     private void CaptureObjectLightmapData()
//     {
//         MeshRenderer[] renderers = FindObjectsOfType<MeshRenderer>();
//
//         foreach (var renderer in renderers)
//         {
//             if (renderer.lightmapIndex >= 0 && renderer.lightmapIndex < LightmapSettings.lightmaps.Length)
//             {
//                 // 为每个材质创建数据（多材质支持）
//                 for (int materialIndex = 0; materialIndex < renderer.sharedMaterials.Length; materialIndex++)
//                 {
//                     LightmapObjectData objectData = new LightmapObjectData
//                     {
//                         gameObjectPath = GetGameObjectPath(renderer.transform),
//                         materialIndex = materialIndex,
//                         lightmapIndex = renderer.lightmapIndex,
//                         lightmapScaleOffset = renderer.lightmapScaleOffset,
//                         hasLightmap = true
//                     };
//
//                     // 检查是否有directional lightmap
//                     if (renderer.lightmapIndex < currentData.lightmapTextures.Count)
//                     {
//                         var textureSet = currentData.lightmapTextures[renderer.lightmapIndex];
//                         objectData.hasDirLightmap = textureSet.lightmapDir != null && currentData.enableDirectionalLightmap;
//                         objectData.hasShadowMask = textureSet.shadowMask != null && currentData.enableShadowMask;
//                     }
//
//                     objectData.hasGpuInstance = CheckGPUInstancingStatus(renderer.sharedMaterials[materialIndex]);
//
//                     currentData.objectData.Add(objectData);
//                 }
//             }
//         }
//     }
//
//     private void CreateRuntimeApplierInScene()
//     {
//         GameObject applierObj = new GameObject("Runtime Lightmap Applier");
//         RuntimeLightmapApplier applier = applierObj.AddComponent<RuntimeLightmapApplier>();
//         if (applier == null)
//         {
//             Debug.LogError("Failed to add RuntimeLightmapApplier component!");
//             return;
//         }
//         applier.lightmapData = currentData;
//
//         Selection.activeGameObject = applierObj;
//
//         Debug.Log("Created Runtime Lightmap Applier in scene");
//     }
//
//     private void DisplayCapturedDataInfo()
//     {
//         if (currentData == null) return;
//
//         EditorGUILayout.LabelField("Captured Data Information", EditorStyles.boldLabel);
//
//         EditorGUILayout.LabelField($"Scene: {currentData.sceneName}");
//         EditorGUILayout.LabelField($"Objects: {currentData.objectData.Count}");
//         EditorGUILayout.LabelField($"Lightmap Textures: {currentData.lightmapTextures.Count}");
//
//         // 显示对象列表
//         showObjectList = EditorGUILayout.Foldout(showObjectList, "Object List");
//         if (showObjectList && currentData.objectData.Count > 0)
//         {
//             EditorGUI.indentLevel++;
//             int displayCount = Mathf.Min(10, currentData.objectData.Count);
//
//             for (int i = 0; i < displayCount; i++)
//             {
//                 var objData = currentData.objectData[i];
//                 EditorGUILayout.LabelField($"{Path.GetFileName(objData.gameObjectPath)} [Mat:{objData.materialIndex}] [LM:{objData.lightmapIndex}]");
//             }
//
//             if (currentData.objectData.Count > displayCount)
//             {
//                 EditorGUILayout.LabelField($"... and {currentData.objectData.Count - displayCount} more");
//             }
//
//             EditorGUI.indentLevel--;
//         }
//     }
//
//     private string GetGameObjectPath(Transform transform)
//     {
//         string path = transform.name;
//         while (transform.parent != null)
//         {
//             transform = transform.parent;
//             path = transform.name + "/" + path;
//         }
//         return path;
//     }
// }
using UnityEngine;
using UnityEditor;
using UnityEngine.SceneManagement;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;

public class RuntimeLightmapCaptureWindow : EditorWindow
{
    private RuntimeLightmapData currentData;
    private Vector2 scrollPosition;
    private bool showCaptureSettings = true;
    private bool showObjectList = false;
    private bool showMaterialSettings = true;

    [MenuItem("Window/Lighting/Runtime Lightmap Capture")]
    public static void ShowWindow()
    {
        GetWindow<RuntimeLightmapCaptureWindow>("Runtime Lightmap Capture");
    }

    private void OnGUI()
    {
        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

        EditorGUILayout.LabelField("Runtime Lightmap Capture Tool", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // 数据资源选择
        EditorGUILayout.BeginHorizontal();
        currentData = EditorGUILayout.ObjectField("Runtime Lightmap Data",
            currentData, typeof(RuntimeLightmapData), false) as RuntimeLightmapData;

        if (GUILayout.Button("Create New", GUILayout.Width(100)))
        {
            CreateNewRuntimeLightmapData();
        }
        EditorGUILayout.EndHorizontal();

        if (currentData == null)
        {
            EditorGUILayout.HelpBox("Please select or create a Runtime Lightmap Data asset to continue.",
                MessageType.Info);
            EditorGUILayout.EndScrollView();
            return;
        }

        EditorGUILayout.Space();

        // 应用模式选择
        EditorGUILayout.LabelField("Apply Mode", EditorStyles.boldLabel);
        currentData.applyMode = (LightmapApplyMode)EditorGUILayout.EnumPopup("Lightmap Apply Mode", currentData.applyMode);

        if (currentData.applyMode == LightmapApplyMode.MaterialGeneration)
        {
            EditorGUILayout.HelpBox("Material Generation mode will create new materials with baked lightmap data. Perfect for SRP compatibility.", MessageType.Info);
        }
        else
        {
            EditorGUILayout.HelpBox("Material Property Block mode uses runtime MPB to apply lightmap data without modifying materials.", MessageType.Info);
        }

        EditorGUILayout.Space();

        // 捕获设置
        showCaptureSettings = EditorGUILayout.Foldout(showCaptureSettings, "Capture Settings");
        if (showCaptureSettings)
        {
            EditorGUI.indentLevel++;
            currentData.enableLightmap = EditorGUILayout.Toggle("Enable Lightmap", currentData.enableLightmap);
            currentData.enableDirectionalLightmap = EditorGUILayout.Toggle("Enable Directional Lightmap", currentData.enableDirectionalLightmap);
            currentData.enableShadowMask = EditorGUILayout.Toggle("Enable Shadow Mask", currentData.enableShadowMask);
            EditorGUI.indentLevel--;
        }

        EditorGUILayout.Space();

        // 材质生成设置（仅在材质球方案时显示）
        if (currentData.applyMode == LightmapApplyMode.MaterialGeneration)
        {
            showMaterialSettings = EditorGUILayout.Foldout(showMaterialSettings, "Material Generation Settings");
            if (showMaterialSettings)
            {
                EditorGUI.indentLevel++;
                EditorGUILayout.HelpBox("Generated materials will be placed in the same folder as the original material with suffix '_Lightmapped'", MessageType.Info);

                if (GUILayout.Button("Clean Generated Materials"))
                {
                    CleanGeneratedMaterials();
                }
                EditorGUI.indentLevel--;
            }
        }

        EditorGUILayout.Space();

        // 主要操作按钮
        if (GUILayout.Button("Capture Scene Lightmap Data", GUILayout.Height(30)))
        {
            CaptureSceneLightmapData();
        }

        if (currentData.applyMode == LightmapApplyMode.MaterialGeneration)
        {
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Generate Lightmap Materials", GUILayout.Height(25)))
            {
                GenerateLightmapMaterials();
            }
            if (GUILayout.Button("Apply Materials to Scene", GUILayout.Height(25)))
            {
                ApplyGeneratedMaterials();
            }
            if (GUILayout.Button("Recover Materials to Scene", GUILayout.Height(25)))
            {
                RecoverMaterials();
            }
            EditorGUILayout.EndHorizontal();
        }

        if (GUILayout.Button("Create Runtime Applier in Scene", GUILayout.Height(25)))
        {
            CreateRuntimeApplierInScene();
        }

        EditorGUILayout.Space();

        // 显示捕获的数据信息
        DisplayCapturedDataInfo();

        EditorGUILayout.EndScrollView();
    }

    private void CreateNewRuntimeLightmapData()
    {
        string sceneName = SceneManager.GetActiveScene().name;
        string path = EditorUtility.SaveFilePanelInProject(
            "Create Runtime Lightmap Data",
            $"RuntimeLightmapData_{sceneName}",
            "asset",
            "Choose location to save runtime lightmap data");

        if (!string.IsNullOrEmpty(path))
        {
            RuntimeLightmapData newData = CreateInstance<RuntimeLightmapData>();
            newData.sceneName = sceneName;
            newData.sceneGUID = AssetDatabase.AssetPathToGUID(SceneManager.GetActiveScene().path);

            AssetDatabase.CreateAsset(newData, path);
            AssetDatabase.SaveAssets();

            currentData = newData;
            Selection.activeObject = newData;
        }
    }

    private void CaptureSceneLightmapData()
    {
        if (currentData == null)
        {
            Debug.LogError("No runtime lightmap data asset selected!");
            return;
        }

        // 清除现有数据
        currentData.objectData.Clear();
        currentData.lightmapTextures.Clear();
        currentData.generatedMaterials.Clear();

        // 更新场景信息
        Scene activeScene = SceneManager.GetActiveScene();
        currentData.sceneName = activeScene.name;
        currentData.sceneGUID = AssetDatabase.AssetPathToGUID(activeScene.path);

        // 捕获环境光设置
        currentData.ambientColor = RenderSettings.ambientLight;
        currentData.ambientIntensity = RenderSettings.ambientIntensity;

        // 捕获lightmap纹理
        CaptureLightmapTextures();

        // 捕获对象数据
        CaptureObjectLightmapData();

        EditorUtility.SetDirty(currentData);
        AssetDatabase.SaveAssets();

        Debug.Log($"Captured lightmap data: {currentData.objectData.Count} objects, {currentData.lightmapTextures.Count} lightmaps");
    }

    private void CaptureLightmapTextures()
    {
        var lightmaps = LightmapSettings.lightmaps;

        for (int i = 0; i < lightmaps.Length; i++)
        {
            LightmapTextureSet textureSet = new LightmapTextureSet
            {
                lightmapColor = lightmaps[i].lightmapColor,
                lightmapDir = lightmaps[i].lightmapDir,
                shadowMask = lightmaps[i].shadowMask
            };

            currentData.lightmapTextures.Add(textureSet);
        }
    }

    private bool CheckGPUInstancingStatus(Material material)
    {
        if (material == null) return false;

        // 检查材质是否启用GPU Instancing
        bool materialEnabled = material.enableInstancing;

        // 检查Shader是否支持GPU Instancing
        bool shaderSupported = material.shader != null && material.shader.isSupported;

        return materialEnabled && shaderSupported;
    }

    private void CaptureObjectLightmapData()
    {
        MeshRenderer[] renderers = FindObjectsOfType<MeshRenderer>();

        foreach (var renderer in renderers)
        {
            if (renderer.lightmapIndex >= 0 && renderer.lightmapIndex < LightmapSettings.lightmaps.Length)
            {
                // 为每个材质创建数据（多材质支持）
                for (int materialIndex = 0; materialIndex < renderer.sharedMaterials.Length; materialIndex++)
                {
                    LightmapObjectData objectData = new LightmapObjectData
                    {
                        gameObjectPath = GetGameObjectPath(renderer.transform),
                        materialIndex = materialIndex,
                        lightmapIndex = renderer.lightmapIndex,
                        lightmapScaleOffset = renderer.lightmapScaleOffset,
                        hasLightmap = true
                    };

                    // 检查是否有directional lightmap
                    if (renderer.lightmapIndex < currentData.lightmapTextures.Count)
                    {
                        var textureSet = currentData.lightmapTextures[renderer.lightmapIndex];
                        objectData.hasDirLightmap = textureSet.lightmapDir != null && currentData.enableDirectionalLightmap;
                        objectData.hasShadowMask = textureSet.shadowMask != null && currentData.enableShadowMask;
                    }

                    objectData.hasGpuInstance = CheckGPUInstancingStatus(renderer.sharedMaterials[materialIndex]);

                    currentData.objectData.Add(objectData);

                    // 为材质球方案记录材质信息
                    if (currentData.applyMode == LightmapApplyMode.MaterialGeneration)
                    {
                        var originalMaterial = renderer.sharedMaterials[materialIndex];
                        if (originalMaterial != null)
                        {
                            string originalPath = AssetDatabase.GetAssetPath(originalMaterial);
                            if (!string.IsNullOrEmpty(originalPath))
                            {
                                LightmapMaterialData materialData = new LightmapMaterialData
                                {
                                    originalMaterialPath = originalPath,
                                    gameObjectPath = objectData.gameObjectPath,
                                    materialIndex = materialIndex
                                };

                                // 检查是否已存在相同的材质记录
                                bool exists = currentData.generatedMaterials.Exists(m =>
                                    m.originalMaterialPath == originalPath &&
                                    m.gameObjectPath == objectData.gameObjectPath &&
                                    m.materialIndex == materialIndex);

                                if (!exists)
                                {
                                    currentData.generatedMaterials.Add(materialData);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    private void GenerateLightmapMaterials()
    {
        if (currentData == null || currentData.applyMode != LightmapApplyMode.MaterialGeneration)
        {
            Debug.LogError("Invalid data or mode for material generation!");
            return;
        }

        int generatedCount = 0;
        EditorUtility.DisplayProgressBar("Generating Lightmap Materials", "Processing...", 0f);

        try
        {
            for (int i = 0; i < currentData.generatedMaterials.Count; i++)
            {
                var materialData = currentData.generatedMaterials[i];
                float progress = (float)i / currentData.generatedMaterials.Count;
                EditorUtility.DisplayProgressBar("Generating Lightmap Materials", $"Processing {Path.GetFileName(materialData.originalMaterialPath)}", progress);

                if (GenerateLightmapMaterial(materialData, i))
                {
                    generatedCount++;
                }
            }
        }
        finally
        {
            EditorUtility.ClearProgressBar();
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"Generated {generatedCount} lightmap materials");
    }

    private bool GenerateLightmapMaterial(LightmapMaterialData materialData, int dataIndex)
    {
        // 加载原始材质
        Material originalMaterial = AssetDatabase.LoadAssetAtPath<Material>(materialData.originalMaterialPath);
        if (originalMaterial == null)
        {
            Debug.LogError($"Could not load original material: {materialData.originalMaterialPath}");
            return false;
        }

        // 查找对应的对象数据
        var objData = currentData.objectData.Find(obj =>
            obj.gameObjectPath == materialData.gameObjectPath &&
            obj.materialIndex == materialData.materialIndex);

        if (objData == null)
        {
            Debug.LogError($"Could not find object data for: {materialData.gameObjectPath}");
            return false;
        }

        // 生成新材质路径
        string originalDir = Path.GetDirectoryName(materialData.originalMaterialPath);
        string originalName = Path.GetFileNameWithoutExtension(materialData.originalMaterialPath);
        string newMaterialPath = Path.Combine(originalDir, $"{originalName}_Lightmapped_{objData.lightmapIndex}.mat").Replace("\\", "/");

        // 创建新材质
        Material newMaterial = new Material(originalMaterial);
        

        // 设置lightmap相关属性
        SetLightmapPropertiesOnMaterial(newMaterial, objData);
        newMaterial.renderQueue = originalMaterial.renderQueue;

        // 保存新材质
        AssetDatabase.CreateAsset(newMaterial, newMaterialPath);

        // 记录生成的材质路径
        materialData.generatedMaterialPath = newMaterialPath;

        return true;
    }
    private void SetLightmapPropertiesOnMaterial(Material material, LightmapObjectData objData)
    {
        if (objData.lightmapIndex >= currentData.lightmapTextures.Count) return;

        var lightmapSet = currentData.lightmapTextures[objData.lightmapIndex];

        Shader newShader = Shader.Find(material.shader.name + "_OM");
        material.shader = newShader==null?material.shader:newShader;
        if (newShader==null)
        {
            // 启用相关Keywords
            material.EnableKeyword("LIGHTMAP_ON");
        }

        // if (Shader.IsKeywordEnabled("_MIXED_LIGHTING_SUBTRACTIVE")) //不需要 是场景动态的参数
        // {
        //     material.EnableKeyword("_MIXED_LIGHTING_SUBTRACTIVE");
        // }

        if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
        {
            material.EnableKeyword("DIRLIGHTMAP_COMBINED");
        }

        if (lightmapSet.shadowMask != null && objData.hasShadowMask)
        {
            material.EnableKeyword("LIGHTMAP_SHADOW_MIXING");
            material.EnableKeyword("SHADOWS_SHADOWMASK");
        }

        // 设置lightmap纹理
        if (lightmapSet.lightmapColor != null)
        {
            material.SetTexture("_Custom_Lightmap", lightmapSet.lightmapColor);
        }

        if (lightmapSet.lightmapDir != null)
        {
            material.SetTexture("unity_LightmapInd", lightmapSet.lightmapDir);
        }

        if (lightmapSet.shadowMask != null)
        {
            material.SetTexture("unity_ShadowMask", lightmapSet.shadowMask);
        }

        // 设置lightmap UV变换
        material.SetVector("_CustomLightmapOffset", objData.lightmapScaleOffset);
        material.SetFloat("_UseCustomLightmapOffset",1);
    }

    private void ApplyGeneratedMaterials()
    {
        if (currentData == null || currentData.applyMode != LightmapApplyMode.MaterialGeneration)
        {
            Debug.LogError("Invalid data or mode for applying materials!");
            return;
        }

        int appliedCount = 0;

        foreach (var materialData in currentData.generatedMaterials)
        {
            if (string.IsNullOrEmpty(materialData.generatedMaterialPath)) continue;

            // 查找目标GameObject
            GameObject targetObj = FindGameObjectByPath(materialData.gameObjectPath);
            if (targetObj == null)
            {
                Debug.LogWarning($"Could not find GameObject: {materialData.gameObjectPath}");
                continue;
            }

            Renderer renderer = targetObj.GetComponent<Renderer>();
            if (renderer == null)
            {
                Debug.LogWarning($"No renderer found on: {materialData.gameObjectPath}");
                continue;
            }

            // 加载生成的材质
            Material generatedMaterial = AssetDatabase.LoadAssetAtPath<Material>(materialData.generatedMaterialPath);
            if (generatedMaterial == null)
            {
                Debug.LogWarning($"Could not load generated material: {materialData.generatedMaterialPath}");
                continue;
            }

            // 替换材质
            Material[] materials = renderer.sharedMaterials;
            if (materialData.materialIndex < materials.Length)
            {
                materials[materialData.materialIndex] = generatedMaterial;
                renderer.sharedMaterials = materials;
                appliedCount++;

                // 标记对象为脏
                EditorUtility.SetDirty(renderer);
            }
        }

        Debug.Log($"Applied {appliedCount} generated materials to scene objects");
    }

    private void RecoverMaterials()
    {
        if (currentData == null || currentData.applyMode != LightmapApplyMode.MaterialGeneration)
        {
            Debug.LogError("Invalid data or mode for applying materials!");
            return;
        }

        int appliedCount = 0;

        foreach (var materialData in currentData.generatedMaterials)
        {
            if (string.IsNullOrEmpty(materialData.originalMaterialPath)) continue;

            // 查找目标GameObject
            GameObject targetObj = FindGameObjectByPath(materialData.gameObjectPath);
            if (targetObj == null)
            {
                Debug.LogWarning($"Could not find GameObject: {materialData.gameObjectPath}");
                continue;
            }

            Renderer renderer = targetObj.GetComponent<Renderer>();
            if (renderer == null)
            {
                Debug.LogWarning($"No renderer found on: {materialData.gameObjectPath}");
                continue;
            }

            // 加载生成的材质
            Material originalMaterial = AssetDatabase.LoadAssetAtPath<Material>(materialData.originalMaterialPath);
            if (originalMaterial == null)
            {
                Debug.LogWarning($"Could not load original material: {materialData.originalMaterialPath}");
                continue;
            }

            // 替换材质
            Material[] materials = renderer.sharedMaterials;
            if (materialData.materialIndex < materials.Length)
            {
                materials[materialData.materialIndex] = originalMaterial;
                renderer.sharedMaterials = materials;
                appliedCount++;

                // 标记对象为脏
                EditorUtility.SetDirty(renderer);
            }
        }
    }

    private void CleanGeneratedMaterials()
    {
        if (currentData == null) return;

        int deletedCount = 0;

        foreach (var materialData in currentData.generatedMaterials)
        {
            if (!string.IsNullOrEmpty(materialData.generatedMaterialPath))
            {
                if (AssetDatabase.DeleteAsset(materialData.generatedMaterialPath))
                {
                    deletedCount++;
                }
            }
        }

        RecoverMaterials(); //恢复到之前的材质

        currentData.generatedMaterials.Clear();
        EditorUtility.SetDirty(currentData);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"Deleted {deletedCount} generated materials");
    }

    private GameObject FindGameObjectByPath(string path)
    {
        string[] pathParts = path.Split('/');
        GameObject current = GameObject.Find(pathParts[0]);

        if (current == null) return null;

        for (int i = 1; i < pathParts.Length; i++)
        {
            Transform child = current.transform.Find(pathParts[i]);
            if (child == null) return null;
            current = child.gameObject;
        }

        return current;
    }

    private void CreateRuntimeApplierInScene()
    {
        GameObject applierObj = new GameObject("Runtime Lightmap Applier");
        RuntimeLightmapApplier applier = applierObj.AddComponent<RuntimeLightmapApplier>();
        if (applier == null)
        {
            Debug.LogError("Failed to add RuntimeLightmapApplier component!");
            return;
        }
        applier.lightmapData = currentData;

        Selection.activeGameObject = applierObj;

        Debug.Log("Created Runtime Lightmap Applier in scene");
    }

    private void DisplayCapturedDataInfo()
    {
        if (currentData == null) return;

        EditorGUILayout.LabelField("Captured Data Information", EditorStyles.boldLabel);

        EditorGUILayout.LabelField($"Scene: {currentData.sceneName}");
        EditorGUILayout.LabelField($"Apply Mode: {currentData.applyMode}");
        EditorGUILayout.LabelField($"Objects: {currentData.objectData.Count}");
        EditorGUILayout.LabelField($"Lightmap Textures: {currentData.lightmapTextures.Count}");

        if (currentData.applyMode == LightmapApplyMode.MaterialGeneration)
        {
            EditorGUILayout.LabelField($"Materials to Generate: {currentData.generatedMaterials.Count}");
        }

        // 显示对象列表
        showObjectList = EditorGUILayout.Foldout(showObjectList, "Object List");
        if (showObjectList && currentData.objectData.Count > 0)
        {
            EditorGUI.indentLevel++;
            int displayCount = Mathf.Min(10, currentData.objectData.Count);

            for (int i = 0; i < displayCount; i++)
            {
                var objData = currentData.objectData[i];
                EditorGUILayout.LabelField($"{Path.GetFileName(objData.gameObjectPath)} [Mat:{objData.materialIndex}] [LM:{objData.lightmapIndex}]");
            }

            if (currentData.objectData.Count > displayCount)
            {
                EditorGUILayout.LabelField($"... and {currentData.objectData.Count - displayCount} more");
            }

            EditorGUI.indentLevel--;
        }
    }

    private string GetGameObjectPath(Transform transform)
    {
        string path = transform.name;
        while (transform.parent != null)
        {
            transform = transform.parent;
            path = transform.name + "/" + path;
        }
        return path;
    }
}