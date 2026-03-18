using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

public class MaterialColorLinearToSRGBConverter : EditorWindow
{
    private List<Material> materials = new List<Material>();
    private Vector2 scrollPos;
    private bool showPreview = true;
    private Dictionary<Material, List<ColorPropertyInfo>> colorProperties = new Dictionary<Material, List<ColorPropertyInfo>>();

    private class ColorPropertyInfo
    {
        public string propertyName;
        public string displayName;
        public Color originalColor;
        public Color convertedColor;
        public bool willConvert;
    }

    [MenuItem("Tools/TempByAI/Material Color Linear to SRGB Converter")]
    public static void ShowWindow()
    {
        GetWindow<MaterialColorLinearToSRGBConverter>("Color Converter");
    }

    private void OnGUI()
    {
        GUILayout.Label("Material Color Linear to SRGB Converter", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // 添加材质区域
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Materials to Convert:", EditorStyles.boldLabel);
        
        // 拖拽区域
        Rect dropArea = GUILayoutUtility.GetRect(0f, 50f, GUILayout.ExpandWidth(true));
        GUI.Box(dropArea, "Drag Materials Here");
        HandleDragAndDrop(dropArea);

        // 批量添加按钮
        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Add Selected Materials"))
        {
            AddSelectedMaterials();
        }
        if (GUILayout.Button("Add Materials from Selected Objects"))
        {
            AddMaterialsFromSelectedObjects();
        }
        if (GUILayout.Button("Clear All"))
        {
            materials.Clear();
            colorProperties.Clear();
        }
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.EndVertical();

        EditorGUILayout.Space();

        // 显示预览选项
        showPreview = EditorGUILayout.Toggle("Show Preview", showPreview);
        EditorGUILayout.Space();

        // 材质列表
        if (materials.Count > 0)
        {
            scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
            
            for (int i = materials.Count - 1; i >= 0; i--)
            {
                if (materials[i] == null)
                {
                    materials.RemoveAt(i);
                    continue;
                }

                DrawMaterialInfo(materials[i], i);
            }

            EditorGUILayout.EndScrollView();

            EditorGUILayout.Space();

            // 转换按钮
            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = Color.green;
            if (GUILayout.Button("Convert All Materials", GUILayout.Height(30)))
            {
                ConvertAllMaterials();
            }
            GUI.backgroundColor = Color.white;
            EditorGUILayout.EndHorizontal();
        }
        else
        {
            EditorGUILayout.HelpBox("No materials added. Drag materials here or use the buttons above.", MessageType.Info);
        }
    }

    private void HandleDragAndDrop(Rect dropArea)
    {
        Event evt = Event.current;
        
        if (!dropArea.Contains(evt.mousePosition))
            return;

        switch (evt.type)
        {
            case EventType.DragUpdated:
            case EventType.DragPerform:
                DragAndDrop.visualMode = DragAndDropVisualMode.Copy;

                if (evt.type == EventType.DragPerform)
                {
                    DragAndDrop.AcceptDrag();

                    foreach (Object draggedObject in DragAndDrop.objectReferences)
                    {
                        if (draggedObject is Material material)
                        {
                            if (!materials.Contains(material))
                            {
                                materials.Add(material);
                                AnalyzeMaterial(material);
                            }
                        }
                    }
                }
                break;
        }
    }

    private void AddSelectedMaterials()
    {
        foreach (Object obj in Selection.objects)
        {
            if (obj is Material material && !materials.Contains(material))
            {
                materials.Add(material);
                AnalyzeMaterial(material);
            }
        }
    }

    private void AddMaterialsFromSelectedObjects()
    {
        foreach (GameObject go in Selection.gameObjects)
        {
            Renderer renderer = go.GetComponent<Renderer>();
            if (renderer != null)
            {
                foreach (Material mat in renderer.sharedMaterials)
                {
                    if (mat != null && !materials.Contains(mat))
                    {
                        materials.Add(mat);
                        AnalyzeMaterial(mat);
                    }
                }
            }
        }
    }

    private void AnalyzeMaterial(Material material)
    {
        if (colorProperties.ContainsKey(material))
            return;

        List<ColorPropertyInfo> properties = new List<ColorPropertyInfo>();
        Shader shader = material.shader;
        
        int propertyCount = ShaderUtil.GetPropertyCount(shader);
        
        for (int i = 0; i < propertyCount; i++)
        {
            if (ShaderUtil.GetPropertyType(shader, i) == ShaderUtil.ShaderPropertyType.Color)
            {
                string propName = ShaderUtil.GetPropertyName(shader, i);
                string displayName = ShaderUtil.GetPropertyDescription(shader, i);
                
                if (material.HasProperty(propName))
                {
                    Color originalColor = material.GetColor(propName);
                    Color convertedColor = LinearToGamma(originalColor);
                    
                    properties.Add(new ColorPropertyInfo
                    {
                        propertyName = propName,
                        displayName = displayName,
                        originalColor = originalColor,
                        convertedColor = convertedColor,
                        willConvert = true
                    });
                }
            }
        }

        colorProperties[material] = properties;
    }

    private void DrawMaterialInfo(Material material, int index)
    {
        EditorGUILayout.BeginVertical("box");
        
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.ObjectField(material, typeof(Material), false);
        
        if (GUILayout.Button("Remove", GUILayout.Width(60)))
        {
            materials.RemoveAt(index);
            colorProperties.Remove(material);
            return;
        }
        EditorGUILayout.EndHorizontal();

        if (!colorProperties.ContainsKey(material))
        {
            AnalyzeMaterial(material);
        }

        if (colorProperties.ContainsKey(material))
        {
            List<ColorPropertyInfo> properties = colorProperties[material];
            
            if (properties.Count > 0)
            {
                EditorGUI.indentLevel++;
                
                foreach (var prop in properties)
                {
                    EditorGUILayout.BeginHorizontal();
                    
                    prop.willConvert = EditorGUILayout.Toggle(prop.willConvert, GUILayout.Width(20));
                    EditorGUILayout.LabelField(prop.displayName, GUILayout.Width(150));
                    
                    if (showPreview)
                    {
                        EditorGUILayout.ColorField(GUIContent.none, prop.originalColor, false, true, false, GUILayout.Width(50));
                        EditorGUILayout.LabelField("→", GUILayout.Width(20));
                        EditorGUILayout.ColorField(GUIContent.none, prop.convertedColor, false, true, false, GUILayout.Width(50));
                    }
                    
                    EditorGUILayout.EndHorizontal();
                }
                
                EditorGUI.indentLevel--;
            }
            else
            {
                EditorGUILayout.LabelField("No color properties found", EditorStyles.miniLabel);
            }
        }

        EditorGUILayout.EndVertical();
        EditorGUILayout.Space();
    }

    private void ConvertAllMaterials()
    {
        if (!EditorUtility.DisplayDialog("Confirm Conversion", 
            $"Are you sure you want to convert {materials.Count} material(s)?\n\nThis action can be undone with Ctrl+Z.", 
            "Convert", "Cancel"))
        {
            return;
        }

        int convertedCount = 0;
        int propertyCount = 0;

        foreach (Material material in materials)
        {
            if (material == null) continue;
            
            if (colorProperties.ContainsKey(material))
            {
                Undo.RecordObject(material, "Convert Material Colors to SRGB");
                
                bool materialConverted = false;
                
                foreach (var prop in colorProperties[material])
                {
                    if (prop.willConvert && material.HasProperty(prop.propertyName))
                    {
                        material.SetColor(prop.propertyName, prop.convertedColor);
                        propertyCount++;
                        materialConverted = true;
                    }
                }
                
                if (materialConverted)
                {
                    EditorUtility.SetDirty(material);
                    convertedCount++;
                }
            }
        }

        AssetDatabase.SaveAssets();
        
        EditorUtility.DisplayDialog("Conversion Complete", 
            $"Successfully converted {propertyCount} color properties in {convertedCount} material(s).", 
            "OK");

        // 重新分析材质以显示新的值
        foreach (Material material in materials)
        {
            if (material != null)
            {
                colorProperties.Remove(material);
                AnalyzeMaterial(material);
            }
        }
    }

    private Color LinearToGamma(Color linearColor)
    {
        return new Color(
            Mathf.LinearToGammaSpace(linearColor.r),
            Mathf.LinearToGammaSpace(linearColor.g),
            Mathf.LinearToGammaSpace(linearColor.b),
            linearColor.a
        );
    }
}