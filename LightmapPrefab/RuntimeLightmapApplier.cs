// using UnityEngine;
// using UnityEngine.Rendering;
// using System.Collections.Generic;
// using System.Collections;
//
// public class RuntimeLightmapApplier : MonoBehaviour
// {
//     [Header("Lightmap Data")]
//     public RuntimeLightmapData lightmapData;
//
//     [Header("Settings")]
//     public bool applyOnStart = true;
//     public bool useGlobalKeywords = true; // 是否使用全局Keywords
//     public bool useMPB = false;  //是否使用mpb设置 主要是针对非srp(因为默认走SRP所有为false)
//
//     private Dictionary<string, MaterialPropertyBlock> materialPropertyBlocks = new Dictionary<string, MaterialPropertyBlock>();
//     private Dictionary<Renderer, MaterialPropertyBlock> rendererPropertyBlocks = new Dictionary<Renderer, MaterialPropertyBlock>();
//
//     // Shader属性ID缓存
//     private static readonly int LightmapST = Shader.PropertyToID("unity_LightmapST");
//     private static readonly int CustomLightmapOffset= Shader.PropertyToID("_CustomLightmapOffset");
//     private static readonly int UseCustomLightmapOffset= Shader.PropertyToID("_UseCustomLightmapOffset");
//     private static readonly int Lightmap = Shader.PropertyToID("unity_Lightmap");
//     private static readonly int LightmapInd = Shader.PropertyToID("unity_LightmapInd");
//     private static readonly int ShadowMask = Shader.PropertyToID("unity_ShadowMask");
//
//     // Keywords
//     private static readonly string LIGHTMAP_ON = "LIGHTMAP_ON";
//     private static readonly string DIRLIGHTMAP_COMBINED = "DIRLIGHTMAP_COMBINED";
//     private static readonly string LIGHTMAP_SHADOW_MIXING = "LIGHTMAP_SHADOW_MIXING";
//     private static readonly string SHADOWS_SHADOWMASK = "SHADOWS_SHADOWMASK";
//     private static readonly string MIXED_LIGHTING_SUBTRACTIVE = "_MIXED_LIGHTING_SUBTRACTIVE";
//
//     private void Start()
//     {
//         if (applyOnStart && lightmapData != null)
//         {
//             ApplyLightmapData();
//         }
//     }
//
//     [ContextMenu("Apply Lightmap Data")]
//     public void ApplyLightmapData()
//     {
//         if (lightmapData == null)
//         {
//             Debug.LogError("Lightmap data is null!");
//             return;
//         }
//
//         StartCoroutine(ApplyLightmapDataCoroutine());
//     }
//
//     private IEnumerator ApplyLightmapDataCoroutine()
//     {
//         // 设置全局Keywords
//         SetGlobalShaderKeywords();
//
//         // 设置环境光
//         RenderSettings.ambientLight = lightmapData.ambientColor;
//         RenderSettings.ambientIntensity = lightmapData.ambientIntensity;
//
//         yield return null; // 等一帧确保场景完全加载
//
//         // 应用lightmap到每个对象
//         foreach (var objData in lightmapData.objectData)
//         {
//             ApplyLightmapToObject(objData);
//             yield return null; // 分帧处理，避免卡顿
//         }
//
//         Debug.Log($"Applied runtime lightmap data for {lightmapData.objectData.Count} objects");
//     }
//
//     private void SetGlobalShaderKeywords()
//     {
//         if (!useGlobalKeywords) return;
//
//         // 清除所有相关keywords
//         Shader.DisableKeyword(LIGHTMAP_ON);
//         Shader.DisableKeyword(DIRLIGHTMAP_COMBINED);
//         Shader.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
//         Shader.DisableKeyword(SHADOWS_SHADOWMASK);
//         
//         Shader.EnableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
//         // 根据数据启用对应keywords
//         if (lightmapData.enableLightmap)
//         {
//             Shader.EnableKeyword(LIGHTMAP_ON);
//         }
//
//         if (lightmapData.enableDirectionalLightmap)
//         {
//             Shader.EnableKeyword(DIRLIGHTMAP_COMBINED);
//         }
//
//         if (lightmapData.enableShadowMask)
//         {
//             Shader.EnableKeyword(LIGHTMAP_SHADOW_MIXING);
//             Shader.EnableKeyword(SHADOWS_SHADOWMASK);
//         }
//     }
//
//     private void ApplyLightmapToObject(LightmapObjectData objData)
//     {
//         GameObject targetObject = FindGameObjectByPath(objData.gameObjectPath);
//         if (targetObject == null)
//         {
//             Debug.LogWarning($"Cannot find object at path: {objData.gameObjectPath}");
//             return;
//         }
//
//         Renderer renderer = targetObject.GetComponent<Renderer>();
//         if (renderer == null)
//         {
//             Debug.LogWarning($"No renderer found on object: {objData.gameObjectPath}");
//             return;
//         }
//         // 如果不使用全局Keywords，为每个材质单独设置
//         if (!useGlobalKeywords)
//         {
//             SetMaterialKeywords(renderer, objData);
//         }
//         if (objData.hasGpuInstance||useMPB)
//         {
//             // 获取或创建MaterialPropertyBlock
//             MaterialPropertyBlock propertyBlock = GetOrCreatePropertyBlock(renderer);
//
//             // 设置lightmap相关属性
//             if (objData.hasLightmap && objData.lightmapIndex < lightmapData.lightmapTextures.Count)
//             {
//                 var lightmapSet = lightmapData.lightmapTextures[objData.lightmapIndex];
//
//                 // 设置lightmap纹理
//                 if (lightmapSet.lightmapColor != null)
//                 {
//                     propertyBlock.SetTexture(Lightmap, lightmapSet.lightmapColor);
//                 }
//
//                 // 设置directional lightmap
//                 if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
//                 {
//                     propertyBlock.SetTexture(LightmapInd, lightmapSet.lightmapDir);
//                 }
//
//                 // 设置shadow mask
//                 if (lightmapSet.shadowMask != null && objData.hasShadowMask)
//                 {
//                     propertyBlock.SetTexture(ShadowMask, lightmapSet.shadowMask);
//                 }
//
//                 // 设置lightmap UV变换
//                 propertyBlock.SetVector(LightmapST, objData.lightmapScaleOffset);
//             }
//             
//             // 应用MaterialPropertyBlock
//             renderer.SetPropertyBlock(propertyBlock, objData.materialIndex);
//         }
//         else
//         {
//             if (objData.hasLightmap && objData.lightmapIndex < lightmapData.lightmapTextures.Count)
//             {
//                 if (Application.isPlaying)
//                 {
//                     var lightmapSet = lightmapData.lightmapTextures[objData.lightmapIndex];
//
//                     // 设置lightmap纹理
//                     if (lightmapSet.lightmapColor != null)
//                     {
//                         renderer.materials[objData.materialIndex].SetTexture(Lightmap, lightmapSet.lightmapColor);
//                     }
//
//                     // 设置directional lightmap
//                     if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
//                     {
//                         renderer.materials[objData.materialIndex].SetTexture(LightmapInd, lightmapSet.lightmapDir);
//                     }
//
//                     // 设置shadow mask
//                     if (lightmapSet.shadowMask != null && objData.hasShadowMask)
//                     {
//                         renderer.materials[objData.materialIndex].SetTexture(ShadowMask, lightmapSet.shadowMask);
//                     }
//
//                     // 设置lightmap UV变换
//                     renderer.materials[objData.materialIndex].SetVector(CustomLightmapOffset, objData.lightmapScaleOffset);
//                     renderer.materials[objData.materialIndex].SetFloat(UseCustomLightmapOffset, 1);
//                 }
//                 else
//                 {
//                     var lightmapSet = lightmapData.lightmapTextures[objData.lightmapIndex];
//
//                     // 设置lightmap纹理
//                     if (lightmapSet.lightmapColor != null)
//                     {
//                         renderer.sharedMaterials[objData.materialIndex].SetTexture(Lightmap, lightmapSet.lightmapColor);
//                     }
//
//                     // 设置directional lightmap
//                     if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
//                     {
//                         renderer.sharedMaterials[objData.materialIndex].SetTexture(LightmapInd, lightmapSet.lightmapDir);
//                     }
//
//                     // 设置shadow mask
//                     if (lightmapSet.shadowMask != null && objData.hasShadowMask)
//                     {
//                         renderer.sharedMaterials[objData.materialIndex].SetTexture(ShadowMask, lightmapSet.shadowMask);
//                     }
//
//                     // 设置lightmap UV变换
//                      renderer.sharedMaterials[objData.materialIndex].SetVector(CustomLightmapOffset, objData.lightmapScaleOffset);
//                      renderer.materials[objData.materialIndex].SetFloat(UseCustomLightmapOffset, 1);
//                 }
//             }
//         }
//
//         
//
//     }
//
//     private MaterialPropertyBlock GetOrCreatePropertyBlock(Renderer renderer)
//     {
//         if (!rendererPropertyBlocks.ContainsKey(renderer))
//         {
//             rendererPropertyBlocks[renderer] = new MaterialPropertyBlock();
//         }
//         return rendererPropertyBlocks[renderer];
//     }
//
//     private void SetMaterialKeywords(Renderer renderer, LightmapObjectData objData)
//     {
//         Material[] materials = renderer.materials;
//         if (objData.materialIndex < materials.Length)
//         {
//             Material material = materials[objData.materialIndex];
//
//             material.EnableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
//             // 启用/禁用keywords
//             if (objData.hasLightmap)
//             {
//                 material.EnableKeyword(LIGHTMAP_ON);
//             }
//             else
//             {
//                 material.DisableKeyword(LIGHTMAP_ON);
//             }
//
//             if (objData.hasDirLightmap)
//             {
//                 material.EnableKeyword(DIRLIGHTMAP_COMBINED);
//             }
//             else
//             {
//                 material.DisableKeyword(DIRLIGHTMAP_COMBINED);
//             }
//
//             if (objData.hasShadowMask)
//             {
//                 material.EnableKeyword(LIGHTMAP_SHADOW_MIXING);
//                 material.EnableKeyword(SHADOWS_SHADOWMASK);
//             }
//             else
//             {
//                 material.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
//                 material.DisableKeyword(SHADOWS_SHADOWMASK);
//             }
//         }
//     }
//
//     private GameObject FindGameObjectByPath(string path)
//     {
//         string[] pathParts = path.Split('/');
//         GameObject current = null;
//         if (this.gameObject.transform.childCount>0) //增加对挂在本身节点的支持 效率也方便预设管理
//         {
//             if (this.gameObject.name.Contains(pathParts[0]))
//             {
//                 current = this.gameObject;
//             }
//             else
//             {
//                 Transform child = gameObject.transform.Find(pathParts[0]);
//                 if (child != null)
//                 {
//                     current = child.gameObject;
//                 }
//             }
//         }
//         if(current==null)
//         {
//             current = GameObject.Find(pathParts[0]);
//         }
//
//         if (current == null) return null;
//
//         for (int i = 1; i < pathParts.Length; i++)
//         {
//             Transform child = current.transform.Find(pathParts[i]);
//             if (child == null) return null;
//             current = child.gameObject;
//         }
//
//         return current;
//     }
//
//     [ContextMenu("Clear Lightmap Data")]
//     public void ClearLightmapData()
//     {
//         // 清除所有MaterialPropertyBlock
//         foreach (var kvp in rendererPropertyBlocks)
//         {
//             if (kvp.Key != null)
//             {
//                 kvp.Key.SetPropertyBlock(null);
//             }
//         }
//
//         rendererPropertyBlocks.Clear();
//         materialPropertyBlocks.Clear();
//
//         // 禁用全局keywords
//         Shader.DisableKeyword(LIGHTMAP_ON);
//         Shader.DisableKeyword(DIRLIGHTMAP_COMBINED);
//         Shader.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
//         Shader.DisableKeyword(SHADOWS_SHADOWMASK);
//         Shader.DisableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
//     }
//
//     private void OnDestroy()
//     {
//         ClearLightmapData();
//     }
// }

using UnityEngine;
using UnityEngine.Rendering;
using System.Collections.Generic;
using System.Collections;
#if UNITY_EDITOR
using UnityEditor;
#endif

[ExecuteAlways]
public class RuntimeLightmapApplier : MonoBehaviour
{
    [Header("Lightmap Data")]
    public RuntimeLightmapData lightmapData;

    [Header("Settings")]
    public bool applyOnStart = true;
    //public bool useGlobalKeywords = true; // 是否使用全局Keywords
    //public bool useMPB = false;  //是否使用mpb设置 主要是针对非srp(因为默认走SRP所有为false)

    [Header("Editor Settings")]
    public bool enableInEditMode = false; // 编辑模式下是否启用

    private Dictionary<string, MaterialPropertyBlock> materialPropertyBlocks = new Dictionary<string, MaterialPropertyBlock>();
    private Dictionary<Renderer, MaterialPropertyBlock> rendererPropertyBlocks = new Dictionary<Renderer, MaterialPropertyBlock>();

    // 编辑器状态跟踪
#if UNITY_EDITOR
    private RuntimeLightmapData lastLightmapData;
    private bool lastEnableInEditMode;
    private bool isEditorUpdateRegistered = false;
#endif

    // Shader属性ID缓存
    private static readonly int LightmapST = Shader.PropertyToID("unity_LightmapST");
    private static readonly int CustomLightmapOffset= Shader.PropertyToID("_CustomLightmapOffset");
    private static readonly int UseCustomLightmapOffset= Shader.PropertyToID("_UseCustomLightmapOffset");
    private static readonly int Lightmap = Shader.PropertyToID("unity_Lightmap");
    private static readonly int LightmapInd = Shader.PropertyToID("unity_LightmapInd");
    private static readonly int ShadowMask = Shader.PropertyToID("unity_ShadowMask");

    // Keywords
    private static readonly string LIGHTMAP_ON = "LIGHTMAP_ON";
    private static readonly string DIRLIGHTMAP_COMBINED = "DIRLIGHTMAP_COMBINED";
    private static readonly string LIGHTMAP_SHADOW_MIXING = "LIGHTMAP_SHADOW_MIXING";
    private static readonly string SHADOWS_SHADOWMASK = "SHADOWS_SHADOWMASK";
    private static readonly string MIXED_LIGHTING_SUBTRACTIVE = "_MIXED_LIGHTING_SUBTRACTIVE";

#if UNITY_EDITOR
    private void OnEnable()
    {
        if (!Application.isPlaying)
        {
            RegisterEditorUpdate();
            // 初始化状态
            lastLightmapData = lightmapData;
            lastEnableInEditMode = enableInEditMode;

            if (enableInEditMode && lightmapData != null)
            {
                EditorApplication.delayCall += () =>
                {
                    if (this != null)
                    {
                       
                        ApplyLightmapDataInEditor();
                    }
                };
            }
        }
    }

    private void OnDisable()
    {
        if (!Application.isPlaying)
        {
            UnregisterEditorUpdate();
            ClearLightmapDataInEditor();
        }
    }

    private void RegisterEditorUpdate()
    {
        if (!isEditorUpdateRegistered)
        {
            EditorApplication.update += EditorUpdate;
            isEditorUpdateRegistered = true;
        }
    }

    private void UnregisterEditorUpdate()
    {
        if (isEditorUpdateRegistered)
        {
            EditorApplication.update -= EditorUpdate;
            isEditorUpdateRegistered = false;
        }
    }

    private void EditorUpdate()
    {
        if (this == null)
        {
            UnregisterEditorUpdate();
            return;
        }

        if (Application.isPlaying)
        {
            UnregisterEditorUpdate();
            return;
        }
        // 检查状态变化
        bool dataChanged = lastLightmapData != lightmapData;
        bool enableStateChanged = lastEnableInEditMode != enableInEditMode;

        // if (enableInEditMode)
        // {
        //     // 在编辑模式下，强制使用全局Keywords和MPB，确保不修改任何资产
        //     SetGlobalShaderKeywordsInEditor();
        // }

        if (dataChanged || enableStateChanged)
        {
            // 如果禁用或数据为空，清除效果
            if (!enableInEditMode || lightmapData == null)
            {
                ClearLightmapDataInEditor();
            }
            // 如果启用且有数据，应用效果
            else if (enableInEditMode && lightmapData != null)
            {
                ApplyLightmapDataInEditor();
            }

            // 更新状态
            lastLightmapData = lightmapData;
            lastEnableInEditMode = enableInEditMode;
        }
    }

    [ContextMenu("Apply Lightmap Data (Editor)")]
    public void ApplyLightmapDataInEditor()
    {
        if (!enableInEditMode)
        {
            Debug.LogWarning("Editor mode is disabled. Enable 'Enable In Edit Mode' to use this feature.");
            return;
        }

        if (lightmapData == null)
        {
            Debug.LogError("Lightmap data is null!");
            return;
        }
        
        // 设置环境光 - 不会修改资产
        //RenderSettings.ambientLight = lightmapData.ambientColor;
        //RenderSettings.ambientIntensity = lightmapData.ambientIntensity;

        // 应用lightmap到每个对象 - 纯MPB方案
        foreach (var objData in lightmapData.objectData)
        {
            ApplyLightmapToObjectInEditor(objData);
        }
        Debug.Log($"[Editor] Applied runtime lightmap data with MPB for {lightmapData.objectData.Count} objects");
    }

    // private void SetGlobalShaderKeywordsInEditor()
    // {
    //     // 清除所有相关keywords
    //     Shader.DisableKeyword(LIGHTMAP_ON);
    //     Shader.DisableKeyword(DIRLIGHTMAP_COMBINED);
    //     Shader.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
    //     Shader.DisableKeyword(SHADOWS_SHADOWMASK);
    //
    //     Shader.EnableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
    //
    //     // 根据数据启用对应keywords
    //     if (lightmapData.enableLightmap)
    //     {
    //         Shader.EnableKeyword(LIGHTMAP_ON);
    //     }
    //
    //     if (lightmapData.enableDirectionalLightmap)
    //     {
    //         Shader.EnableKeyword(DIRLIGHTMAP_COMBINED);
    //     }
    //
    //     if (lightmapData.enableShadowMask)
    //     {
    //         Shader.EnableKeyword(LIGHTMAP_SHADOW_MIXING);
    //         Shader.EnableKeyword(SHADOWS_SHADOWMASK);
    //     }
    // }

    private void ApplyLightmapToObjectInEditor(LightmapObjectData objData)
    {
        GameObject targetObject = FindGameObjectByPath(objData.gameObjectPath);
        if (targetObject == null)
        {
            Debug.LogWarning($"Cannot find object at path: {objData.gameObjectPath}");
            return;
        }

        Renderer renderer = targetObject.GetComponent<Renderer>();
        if (renderer == null)
        {
            Debug.LogWarning($"No renderer found on object: {objData.gameObjectPath}");
            return;
        }

        // 编辑模式下强制使用MaterialPropertyBlock，确保不修改材质资产
        ApplyLightmapWithMPBInEditor(renderer, objData);
    }

    private void ApplyLightmapWithMPBInEditor(Renderer renderer, LightmapObjectData objData)
    {
        // 获取或创建MaterialPropertyBlock
        MaterialPropertyBlock propertyBlock = GetOrCreatePropertyBlock(renderer);

        // 设置lightmap相关属性
        if (objData.hasLightmap && objData.lightmapIndex < lightmapData.lightmapTextures.Count)
        {
            var lightmapSet = lightmapData.lightmapTextures[objData.lightmapIndex];

            // 设置lightmap纹理
            if (lightmapSet.lightmapColor != null)
            {
                propertyBlock.SetTexture(Lightmap, lightmapSet.lightmapColor);
            }

            // 设置directional lightmap
            if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
            {
                propertyBlock.SetTexture(LightmapInd, lightmapSet.lightmapDir);
            }

            // 设置shadow mask
            if (lightmapSet.shadowMask != null && objData.hasShadowMask)
            {
                propertyBlock.SetTexture(ShadowMask, lightmapSet.shadowMask);
            }

            // 设置lightmap UV变换
            propertyBlock.SetVector(LightmapST, objData.lightmapScaleOffset);
        }

        // 应用MaterialPropertyBlock
        renderer.SetPropertyBlock(propertyBlock, objData.materialIndex);
        
        if (objData.materialIndex < renderer.materials.Length)  //keyword没办法必须设置材质上
        {
            Material material = renderer.sharedMaterials[objData.materialIndex];

            //material.EnableKeyword(MIXED_LIGHTING_SUBTRACTIVE); 不需要设置，毕竟它是根据场景是否有Mix光源逻辑设定 
 
            // 启用/禁用keywords
            if (objData.hasLightmap)
            {
                material.EnableKeyword(LIGHTMAP_ON);
            }
            else
            {
                material.DisableKeyword(LIGHTMAP_ON);
            }

            if (objData.hasDirLightmap)
            {
                material.EnableKeyword(DIRLIGHTMAP_COMBINED);
            }
            else
            {
                material.DisableKeyword(DIRLIGHTMAP_COMBINED);
            }
            
            if (objData.hasShadowMask)
            {
                material.EnableKeyword(LIGHTMAP_SHADOW_MIXING);
                material.EnableKeyword(SHADOWS_SHADOWMASK);
            }
            else
            {
                material.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
                material.DisableKeyword(SHADOWS_SHADOWMASK);
            }
        }
    }

    [ContextMenu("Clear Lightmap Data (Editor)")]
    public void ClearLightmapDataInEditor()
    {
        if (!Application.isPlaying)
        {
            ClearLightmapData();
            Debug.Log("[Editor] Cleared lightmap data with MPB");
            ClearMaterialInEditor();
        }
    }

    public void ClearMaterialInEditor()
    {
        foreach (var objData in lightmapData.objectData)
        {
            GameObject targetObject = FindGameObjectByPath(objData.gameObjectPath);
            if (targetObject == null)
            {
                Debug.LogWarning($"Cannot find object at path: {objData.gameObjectPath}");
                return;
            }
            Renderer renderer = targetObject.GetComponent<Renderer>();
            if (objData.materialIndex < renderer.sharedMaterials.Length)
            {
                Material material = renderer.sharedMaterials[objData.materialIndex];

                //material.DisableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
                material.DisableKeyword(LIGHTMAP_ON);
                material.DisableKeyword(DIRLIGHTMAP_COMBINED);
                material.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
                material.DisableKeyword(SHADOWS_SHADOWMASK);
            }
        }
    }

    private void OnDestroy()
    {
        if (!Application.isPlaying)
        {
            UnregisterEditorUpdate();
            ClearMaterialInEditor();
        }
        ClearLightmapData();
    }

    private void OnValidate()
    {
        // OnValidate中只更新状态，实际应用在EditorUpdate中处理
        if (!Application.isPlaying)
        {
            RegisterEditorUpdate();
        }
    }
#endif

    private void Start()
    {
        // 运行时启动
        if (Application.isPlaying && applyOnStart && lightmapData != null)
        {
            ApplyLightmapData();
        }
    }

    [ContextMenu("Apply Lightmap Data")]
    public void ApplyLightmapData()
    {
        if (lightmapData == null)
        {
            Debug.LogError("Lightmap data is null!");
            return;
        }

#if UNITY_EDITOR
        if (!Application.isPlaying && enableInEditMode)
        {
            ApplyLightmapDataInEditor();
            return;
        }
#endif

        if (Application.isPlaying)
        {
            if(transform.childCount > 0)
            {
                ApplyLightmapDataRuntime();
            }
            else
            {
                StartCoroutine(ApplyLightmapDataCoroutine());
            }
        }
    }

    private void ApplyLightmapDataRuntime()
    { 
        foreach (var objData in lightmapData.objectData)
        {
            ApplyLightmapToObject(objData);
        }
    }
    private IEnumerator ApplyLightmapDataCoroutine()
    {
        // 设置全局Keywords
        //SetGlobalShaderKeywords();

        // 设置环境光
        //RenderSettings.ambientLight = lightmapData.ambientColor;
        //RenderSettings.ambientIntensity = lightmapData.ambientIntensity;

        yield return null; // 等一帧确保场景完全加载

        // 应用lightmap到每个对象
        foreach (var objData in lightmapData.objectData)
        {
            ApplyLightmapToObject(objData);
            //yield return null; // 分帧处理，避免卡顿
        }

        //Debug.Log($"[Runtime] Applied runtime lightmap data for {lightmapData.objectData.Count} objects");
    }

    // private void SetGlobalShaderKeywords()
    // {
    //     if (!useGlobalKeywords) return;
    //
    //     // 清除所有相关keywords
    //     Shader.DisableKeyword(LIGHTMAP_ON);
    //     Shader.DisableKeyword(DIRLIGHTMAP_COMBINED);
    //     Shader.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
    //     Shader.DisableKeyword(SHADOWS_SHADOWMASK);
    //
    //     Shader.EnableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
    //     // 根据数据启用对应keywords
    //     if (lightmapData.enableLightmap)
    //     {
    //         Shader.EnableKeyword(LIGHTMAP_ON);
    //     }
    //
    //     if (lightmapData.enableDirectionalLightmap)
    //     {
    //         Shader.EnableKeyword(DIRLIGHTMAP_COMBINED);
    //     }
    //
    //     if (lightmapData.enableShadowMask)
    //     {
    //         Shader.EnableKeyword(LIGHTMAP_SHADOW_MIXING);
    //         Shader.EnableKeyword(SHADOWS_SHADOWMASK);
    //     }
    // }

    private void ApplyLightmapToObject(LightmapObjectData objData)
    {
        GameObject targetObject = FindGameObjectByPath(objData.gameObjectPath);
        if (targetObject == null)
        {
            Debug.LogWarning($"Cannot find object at path: {objData.gameObjectPath}");
            return;
        }

        Renderer renderer = targetObject.GetComponent<Renderer>();
        if (renderer == null)
        {
            Debug.LogWarning($"No renderer found on object: {objData.gameObjectPath}");
            return;
        }

        if (objData.hasGpuInstance)
        {
            // 使用MaterialPropertyBlock方式
            ApplyLightmapWithMPB(renderer, objData);
        }
        else
        {
            // 直接修改材质方式
            ApplyLightmapWithMaterial(renderer, objData);
        }

        // 如果不使用全局Keywords，为每个材质单独设置
        // if (!useGlobalKeywords)
        // {
        //     SetMaterialKeywords(renderer, objData);
        // }
        SetMaterialKeywords(renderer, objData);
    }

    private void ApplyLightmapWithMPB(Renderer renderer, LightmapObjectData objData)
    {
        // 获取或创建MaterialPropertyBlock
        MaterialPropertyBlock propertyBlock = GetOrCreatePropertyBlock(renderer);

        // 设置lightmap相关属性
        if (objData.hasLightmap && objData.lightmapIndex < lightmapData.lightmapTextures.Count)
        {
            var lightmapSet = lightmapData.lightmapTextures[objData.lightmapIndex];

            // 设置lightmap纹理
            if (lightmapSet.lightmapColor != null)
            {
                propertyBlock.SetTexture(Lightmap, lightmapSet.lightmapColor);
            }

            // 设置directional lightmap
            if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
            {
                propertyBlock.SetTexture(LightmapInd, lightmapSet.lightmapDir);
            }

            // 设置shadow mask
            if (lightmapSet.shadowMask != null && objData.hasShadowMask)
            {
                propertyBlock.SetTexture(ShadowMask, lightmapSet.shadowMask);
            }

            // 设置lightmap UV变换
            propertyBlock.SetVector(LightmapST, objData.lightmapScaleOffset);
        }

        // 应用MaterialPropertyBlock
        renderer.SetPropertyBlock(propertyBlock, objData.materialIndex);
    }

    private void ApplyLightmapWithMaterial(Renderer renderer, LightmapObjectData objData)
    {
        if (objData.hasLightmap && objData.lightmapIndex < lightmapData.lightmapTextures.Count)
        {
            var lightmapSet = lightmapData.lightmapTextures[objData.lightmapIndex];
            Material targetMaterial = null;

            // 运行时使用materials，会创建实例
            if (objData.materialIndex < renderer.materials.Length)
            {
                targetMaterial = renderer.materials[objData.materialIndex];
            }

            if (targetMaterial != null)
            {
                // 设置lightmap纹理
                if (lightmapSet.lightmapColor != null)
                {
                    targetMaterial.SetTexture(Lightmap, lightmapSet.lightmapColor);
                }

                // 设置directional lightmap
                if (lightmapSet.lightmapDir != null && objData.hasDirLightmap)
                {
                    targetMaterial.SetTexture(LightmapInd, lightmapSet.lightmapDir);
                }

                // 设置shadow mask
                if (lightmapSet.shadowMask != null && objData.hasShadowMask)
                {
                    targetMaterial.SetTexture(ShadowMask, lightmapSet.shadowMask);
                }

                // 设置lightmap UV变换
                targetMaterial.SetVector(CustomLightmapOffset, objData.lightmapScaleOffset);
                targetMaterial.SetFloat( UseCustomLightmapOffset,1);
            }
        }
    }

    private MaterialPropertyBlock GetOrCreatePropertyBlock(Renderer renderer)
    {
        if (!rendererPropertyBlocks.ContainsKey(renderer))
        {
            rendererPropertyBlocks[renderer] = new MaterialPropertyBlock();
        }
        return rendererPropertyBlocks[renderer];
    }

    private void SetMaterialKeywords(Renderer renderer, LightmapObjectData objData)
    {
        // 运行时才修改材质Keywords
        if (Application.isPlaying && objData.materialIndex < renderer.materials.Length)
        {
            Material material = renderer.materials[objData.materialIndex];

            //material.EnableKeyword(MIXED_LIGHTING_SUBTRACTIVE);

            // 启用/禁用keywords
            if (objData.hasLightmap)
            {
                material.EnableKeyword(LIGHTMAP_ON);
            }
            else
            {
                material.DisableKeyword(LIGHTMAP_ON);
            }

            if (objData.hasDirLightmap)
            {
                material.EnableKeyword(DIRLIGHTMAP_COMBINED);
            }
            else
            {
                material.DisableKeyword(DIRLIGHTMAP_COMBINED);
            }

            if (objData.hasShadowMask)
            {
                material.EnableKeyword(LIGHTMAP_SHADOW_MIXING);
                material.EnableKeyword(SHADOWS_SHADOWMASK);
            }
            else
            {
                material.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
                material.DisableKeyword(SHADOWS_SHADOWMASK);
            }
        }
    }
    
    private GameObject FindGameObjectByPath(string path)
    {
        string[] pathParts = path.Split('/');
        GameObject current = null;

        if (this.gameObject.transform.childCount > 0) //增加对挂在本身节点的支持 效率也方便预设管理
        {
            if (this.gameObject.name.Contains(pathParts[0]))
            {
                current = this.gameObject;
            }
            else
            {
                Transform child = gameObject.transform.Find(pathParts[0]);
                if (child != null)
                {
                    current = child.gameObject;
                }
            }
        }

        if (current == null)
        {
            current = GameObject.Find(pathParts[0]);
        }

        if (current == null) return null;

        for (int i = 1; i < pathParts.Length; i++)
        {
            Transform child = current.transform.Find(pathParts[i]);
            if (child == null) return null;
            current = child.gameObject;
        }

        return current;
    }

    [ContextMenu("Clear Lightmap Data")]
    public void ClearLightmapData()
    {
        // 清除所有MaterialPropertyBlock
        foreach (var kvp in rendererPropertyBlocks)
        {
            if (kvp.Key != null)
            {
                kvp.Key.SetPropertyBlock(null);
            }
        }

        rendererPropertyBlocks.Clear();
        materialPropertyBlocks.Clear();

        // 禁用全局keywords   //没用不支持 LIGHTMAP_ON 在管线里会被刷新
        // Shader.DisableKeyword(LIGHTMAP_ON);
        // Shader.DisableKeyword(DIRLIGHTMAP_COMBINED);
        // Shader.DisableKeyword(LIGHTMAP_SHADOW_MIXING);
        // Shader.DisableKeyword(SHADOWS_SHADOWMASK);
        // Shader.DisableKeyword(MIXED_LIGHTING_SUBTRACTIVE);
    }
}