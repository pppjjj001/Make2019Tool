using UnityEditor;
using UnityEngine;
using System.Collections.Generic;

public class URPShaderConverter : EditorWindow
{
    private static readonly Dictionary<string, string> PropertyMappings = new Dictionary<string, string>
    {
        {"_MainTex", "_BaseMap"},
        {"_Color", "_BaseColor"},
        {"_MetallicGlossMap", "_MetallicGlossMap"},
        {"_Metallic", "_Metallic"},
        {"_Glossiness", "_Smoothness"},
        {"_BumpMap", "_BumpMap"},
        {"_BumpScale", "_BumpScale"},
        {"_OcclusionMap", "_OcclusionMap"},
        {"_OcclusionStrength", "_OcclusionStrength"}
    };

    [MenuItem("Tools/URP材质批量转换")]
    public static void ShowWindow()
    {
        GetWindow<URPShaderConverter>("URP材质转换器");
    }

    private Shader urpLitShader;

    void OnGUI()
    {
        urpLitShader = (Shader)EditorGUILayout.ObjectField("目标URP Shader", urpLitShader, typeof(Shader), false);

        if (GUILayout.Button("转换选中材质"))
        {
            ConvertMaterials();
        }
    }

    private void ConvertMaterials()
    {
        if (!urpLitShader)
        {
            Debug.LogError("请先指定URP Lit Shader");
            return;
        }

        var materials = Selection.GetFiltered<Material>(SelectionMode.DeepAssets);
        int progress = 0;

        foreach (var mat in materials)
        {
            EditorUtility.DisplayProgressBar("材质转换中", $"正在处理 {mat.name}", (float)progress++ / materials.Length);

            try
            {
                Undo.RecordObject(mat, "Convert to URP");
                ConvertMaterial(mat);
                EditorUtility.SetDirty(mat);
            }
            catch (System.Exception e)
            {
                Debug.LogError($"转换失败 {mat.name}: {e.Message}");
            }
        }

        AssetDatabase.SaveAssets();
        EditorUtility.ClearProgressBar();
    }

    private void ConvertMaterial(Material mat)
    {
        // 跳过非Standard材质
        if (!mat.shader.name.Contains("Standard")) return;

        // 创建新材质实例
        Material newMat = new Material(urpLitShader)
        {
            name = mat.name + "_URP",
            enableInstancing = mat.enableInstancing
        };

        // 复制材质属性
        foreach (var mapping in PropertyMappings)
        {
            if (mat.HasProperty(mapping.Key))
            {
                if (mat.GetTexture(mapping.Key))
                {
                    newMat.SetTexture(mapping.Value, mat.GetTexture(mapping.Key));
                }
                else
                {
                    newMat.SetColor(mapping.Value, mat.GetColor(mapping.Key));
                }
            }
        }

        // 处理特殊属性
        if (mat.HasProperty("_GlossMapScale"))
        {
            newMat.SetFloat("_Smoothness", mat.GetFloat("_GlossMapScale"));
        }

        // 保存材质
        string path = AssetDatabase.GetAssetPath(mat);
        AssetDatabase.CreateAsset(newMat, path.Replace(".mat", "_URP.mat"));
    }


    [MenuItem("Tools/替换URP材质")]
    public static void ReplaceMaterialsWithURP()
    {
        if (Selection.activeGameObject == null)
        {
            Debug.LogWarning("请先在场景中选择一个GameObject");
            return;
        }

        //Undo.RecordObjects(GetAllRenderers(Selection.activeGameObject), "Replace URP Materials");

        ReplaceMaterialsForGameObject(Selection.activeGameObject);
        foreach (GameObject go in GetAllChildren(Selection.activeGameObject.transform))
        {
            ReplaceMaterialsForGameObject(go);
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
    }

    static List<Renderer> GetAllRenderers(GameObject root)
    {
        List<Renderer> renderers = new List<Renderer>();
        foreach (Transform child in root.GetComponentsInChildren<Transform>(true))
        {
            if (child.TryGetComponent<Renderer>(out var renderer))
            {
                renderers.Add(renderer);
            }
        }
        return renderers;
    }

    static List<GameObject> GetAllChildren(Transform parent)
    {
        List<GameObject> children = new List<GameObject>();
        for (int i = 0; i < parent.childCount; i++)
        {
            Transform child = parent.GetChild(i);
            children.Add(child.gameObject);
            children.AddRange(GetAllChildren(child));
        }
        return children;
    }

    static void ReplaceMaterialsForGameObject(GameObject go)
    {
        Renderer renderer = go.GetComponent<Renderer>();
        if (renderer == null) return;

        Material[] sharedMaterials = renderer.sharedMaterials;
        bool modified = false;

        for (int i = 0; i < sharedMaterials.Length; i++)
        {
            Material originalMat = sharedMaterials[i];
            if (originalMat == null) continue;

            string path = AssetDatabase.GetAssetPath(originalMat);
            string urpPath = System.IO.Path.Combine(
                System.IO.Path.GetDirectoryName(path),
                System.IO.Path.GetFileNameWithoutExtension(path) + "_URP.mat");

            Material urpMat = AssetDatabase.LoadAssetAtPath<Material>(urpPath);

            if (urpMat != null && urpMat != originalMat)
            {
                sharedMaterials[i] = urpMat;
                modified = true;
            }
        }

        if (modified)
        {
            renderer.sharedMaterials = sharedMaterials;
        }
    }
}