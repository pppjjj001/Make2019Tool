// MatCapPreview.shader
// 放置路径: Assets/Shaders/Custom/MatCapPreview.shader

Shader "Custom/URP/MatCapPreview"
{
    Properties
    {
        _MatCapTex ("MatCap", 2D) = "white" {}
        _Intensity ("Intensity", Range(0, 2)) = 1
    }
    
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" }
        
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            
            TEXTURE2D(_MatCapTex);
            SAMPLER(sampler_MatCapTex);
            
            float _Intensity;
            
            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
            };
            
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 matCapUV : TEXCOORD0;
            };
            
            Varyings vert(Attributes input)
            {
                Varyings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                
                // 视图空间法线
                float3 normalVS = TransformWorldToViewDir(TransformObjectToWorldNormal(input.normalOS), true);
                output.matCapUV = normalVS.xy * 0.5 + 0.5;
                
                return output;
            }
            
            float4 frag(Varyings input) : SV_Target
            {
                float4 matcap = SAMPLE_TEXTURE2D(_MatCapTex, sampler_MatCapTex, input.matCapUV);
                return float4(matcap.rgb * _Intensity, 1);
            }
            
            ENDHLSL
        }
    }
}
