using UnityEngine;
using System.Collections.Generic;
using System;

[Serializable]
public class LightmapObjectData
{
    public string gameObjectPath;
    public int materialIndex; // 多材质时的索引
    public int lightmapIndex;
    public Vector4 lightmapScaleOffset;
    public bool hasLightmap;
    public bool hasDirLightmap;
    public bool hasShadowMask;
    public bool hasGpuInstance;
}

[Serializable]
public class LightmapTextureSet
{
    public Texture2D lightmapColor;
    public Texture2D lightmapDir;
    public Texture2D shadowMask;
}
// 在 RuntimeLightmapData.cs 中添加新的枚举和字段

public enum LightmapApplyMode
{
    MaterialPropertyBlock,  // MPB方案
    MaterialGeneration      // 材质球方案
}

[Serializable]
public class LightmapMaterialData
{
    public string originalMaterialPath;
    public string generatedMaterialPath;
    public string gameObjectPath;
    public int materialIndex;
}



[CreateAssetMenu(fileName = "RuntimeLightmapData", menuName = "Lighting/Runtime Lightmap Data")]
public class RuntimeLightmapData : ScriptableObject
{
    // 在 RuntimeLightmapData 类中添加：
    [Header("Material Generation Settings")]
    public LightmapApplyMode applyMode = LightmapApplyMode.MaterialPropertyBlock;
    public List<LightmapMaterialData> generatedMaterials = new List<LightmapMaterialData>();
    
    [Header("Scene Information")]
    public string sceneName;
    public string sceneGUID;

    [Header("Lightmap Textures")]
    public List<LightmapTextureSet> lightmapTextures = new List<LightmapTextureSet>();

    [Header("Object Data")]
    public List<LightmapObjectData> objectData = new List<LightmapObjectData>();

    [Header("Shader Keywords")]
    public bool enableLightmap = true;
    public bool enableDirectionalLightmap = true;
    public bool enableShadowMask = false;

    [Header("Global Settings")]
    public Color ambientColor = Color.gray;
    public float ambientIntensity = 1.0f;
}