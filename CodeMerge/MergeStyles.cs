using UnityEngine;
using UnityEditor;

namespace CodeMerge
{
    public static partial class MergeStyles
    {
        private static GUIStyle _lineNumberStyle;
        private static GUIStyle _codeStyle;
        private static GUIStyle _addedLineStyle;
        private static GUIStyle _removedLineStyle;
        private static GUIStyle _conflictLineStyle;
        private static GUIStyle _headerStyle;
        private static GUIStyle _toolbarButtonStyle;
        
        public static GUIStyle LineNumberStyle
        {
            get
            {
                if (_lineNumberStyle == null)
                {
                    _lineNumberStyle = new GUIStyle(EditorStyles.label)
                    {
                        alignment = TextAnchor.MiddleRight,
                        normal = { textColor = Color.gray },
                        fontSize = 11,
                        padding = new RectOffset(0, 5, 0, 0)
                    };
                }
                return _lineNumberStyle;
            }
        }
        
        public static GUIStyle CodeStyle
        {
            get
            {
                if (_codeStyle == null)
                {
                    _codeStyle = new GUIStyle(EditorStyles.label)
                    {
                        font = GetMonospaceFont(),
                        fontSize = 12,
                        wordWrap = false,
                        richText = true,
                        padding = new RectOffset(5, 5, 2, 2)
                    };
                }
                return _codeStyle;
            }
        }
        
        public static GUIStyle AddedLineStyle
        {
            get
            {
                if (_addedLineStyle == null)
                {
                    _addedLineStyle = new GUIStyle(CodeStyle);
                    _addedLineStyle.normal.background = MakeTexture(new Color(0.2f, 0.5f, 0.2f, 0.3f));
                }
                return _addedLineStyle;
            }
        }
        
        public static GUIStyle RemovedLineStyle
        {
            get
            {
                if (_removedLineStyle == null)
                {
                    _removedLineStyle = new GUIStyle(CodeStyle);
                    _removedLineStyle.normal.background = MakeTexture(new Color(0.5f, 0.2f, 0.2f, 0.3f));
                }
                return _removedLineStyle;
            }
        }
        
        public static GUIStyle ConflictLineStyle
        {
            get
            {
                if (_conflictLineStyle == null)
                {
                    _conflictLineStyle = new GUIStyle(CodeStyle);
                    _conflictLineStyle.normal.background = MakeTexture(new Color(0.6f, 0.4f, 0.1f, 0.3f));
                }
                return _conflictLineStyle;
            }
        }
        
        public static GUIStyle HeaderStyle
        {
            get
            {
                if (_headerStyle == null)
                {
                    _headerStyle = new GUIStyle(EditorStyles.boldLabel)
                    {
                        fontSize = 14,
                        alignment = TextAnchor.MiddleCenter,
                        normal = { textColor = EditorGUIUtility.isProSkin ? Color.white : Color.black }
                    };
                }
                return _headerStyle;
            }
        }
        
        public static Color AddedColor => new Color(0.3f, 0.7f, 0.3f);
        public static Color RemovedColor => new Color(0.7f, 0.3f, 0.3f);
        public static Color ConflictColor => new Color(0.8f, 0.6f, 0.2f);
        public static Color ModifiedColor => new Color(0.3f, 0.5f, 0.8f);
        
        private static Font GetMonospaceFont()
        {
            return Font.CreateDynamicFontFromOSFont("Consolas", 12);
        }
        
        public static Texture2D MakeTexture(Color color)
        {
            var texture = new Texture2D(1, 1);
            texture.SetPixel(0, 0, color);
            texture.Apply();
            return texture;
        }
        
        public static void RefreshStyles()
        {
            _lineNumberStyle = null;
            _codeStyle = null;
            _addedLineStyle = null;
            _removedLineStyle = null;
            _conflictLineStyle = null;
            _headerStyle = null;
        }
    }
}
