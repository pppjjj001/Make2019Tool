// HairVertexColorPreview.shader
Shader "Custom/HairVertexColorPreview"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _PreviewMode ("Preview Mode", Range(0, 4)) = 2
    }
    
    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }
        
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            
            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
            };
            
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
            };
            
            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);
            
            float _PreviewMode;
            
            Varyings vert(Attributes input)
            {
                Varyings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = input.uv;
                output.color = input.color;
                return output;
            }
            
            half4 frag(Varyings input) : SV_Target
            {
                // Mode 0: 显示完整顶点色
                // Mode 1: 只显示R通道
                // Mode 2: 只显示B通道（UV差值）
                // Mode 3: 显示UV的V值
                
                if (_PreviewMode < 0.5)
                {
                    return input.color;
                }
                else if (_PreviewMode < 1.5)
                {
                    return float4(input.color.rrr, 1);
                }
                else if (_PreviewMode < 2.5)
                {
                    // 显示B通道 - UV差值
                    // 根部（差值大）显示为红色，尖端（差值小）显示为蓝色
                    float diff = input.color.b;
                    return float4(diff, 0, 1 - diff, 1);
                }
                else if (_PreviewMode < 3.5)
                {
                    float uvd = input.uv.y+input.color.b;
                    return float4(uvd, uvd, uvd, 1);
                }
                else
                {
                    // 直接显示UV V值
                    return float4(input.uv.y, input.uv.y, input.uv.y, 1);
                }
            }
            ENDHLSL
        }
    }
}
