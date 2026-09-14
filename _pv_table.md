# PlusVibe — цены с настоящими идентификаторами

Файл содержит реальные id; слой отображения скрывает только часть из них
(у Anthropic — целиком). Поэтому рядом длина и sha1.

| производитель | вариант | model id | len | sha1 | вход ₽/1М | выход ₽/1М | кеш-чт | vision | контекст |
|---|---|---|---|---|---|---|---|---|---|
| DeepSeek | Free | `deepseek-v4-flash-0731:free` | 27 | dd8a3afe8e | 0 | 0 | 0 | да | да |
| MiniMax | Free | `minimax-m2.7:free` | 17 | b581092076 | 0 | 0 | 0 | да | — |
| DeepSeek | Cxb · по умолчанию | `deepseek-v4.1-flash` | 19 | 9ab9da1f08 | 0.76 | 3.02 | 0.08 | да | да |
| DeepSeek | Cxbc | `deepseek-v4.1-flash:cxbc` | 24 | dbeaf9a9f8 | 0.95 | 3.78 | 0.1 | да | да |
| DeepSeek | Network · по умолчанию | `deepseek/deepseek-v4-flash-0731` | 31 | 3e701c8c53 | 2.05 | 6.14 | 0.04 | да | да |
| DeepSeek | Cxbc | `deepseek/deepseek-v4-flash-0731:cxbc` | 36 | f3b4e1a6ad | 2.05 | 6.14 | 0.21 | да | да |
| MiniMax | Network · по умолчанию | `minimax/minimax-m2.7` | 20 | 35c9f04e4f | 1.88 | 6.63 | 0.38 | да | — |
| Meta | Cxmc · по умолчанию | `muse-spark-1.3-contributor` | 26 | f523a201b9 | 3.77 | 7.54 | 0.38 | — | — |
| Zhipu AI | Network | `z-ai/glm-5.2:network` | 20 | 6be22f613e | 2.42 | 8.5 | 0.62 | — | да |
| Zhipu AI | Cxa · по умолчанию | `z-ai/glm-5.2` | 12 | 9189abcca4 | 2.96 | 9.3 | 0.3 | — | да |
| MiniMax | Network · по умолчанию | `minimax/minimax-m2.5` | 20 | 326764c63f | 2.86 | 11.45 | 0.29 | да | да |
| Xiaomi | Network · по умолчанию | `xiaomi/mimo-v2.5` | 16 | 9a90dcd7ff | 6 | 12 | 0.6 | да | да |
| OpenAI | Cx | `openai/gpt-5.6-luna` | 19 | de02b881e9 | 2.64 | 15.84 | 0.26 | да | да |
| OpenAI | Cxb · по умолчанию | `openai/gpt-5.6-luna:cxb` | 23 | e527e9e82c | 2.64 | 15.84 | 0.26 | да | да |
| XAI | Network · по умолчанию | `grok-4.3` | 8 | 3bb9e27c27 | 9.31 | 18.61 | 1 | да | да |
| Google | Ag · по умолчанию | `google/gemini-3.8-flash` | 23 | 4f91698118 | 3.78 | 18.86 | 0.38 | — | да |
| Mistral AI | Вариант 1 · по умолчанию | `mistral-small` | 13 | 565ef1d077 | 8 | 21 | — | да | — |
| Google | Ag · по умолчанию | `google/gemini-3.7-flash` | 23 | b30b3ff324 | 4.4 | 22 | 0.44 | — | да |
| Google | Network | `google/gemini-3.8-flash:network` | 31 | 2868378b73 | 4.72 | 23.58 | 0.47 | — | да |
| OpenAI | Network | `openai/gpt-5.6-luna:network` | 27 | 0b04f34bca | 3.97 | 23.83 | 0.4 | да | да |
| XAI | Network · по умолчанию | `x-ai/grok-4.6` | 13 | 6cd105407a | 8.52 | 25.55 | 0.85 | да | да |
| XAI | Network · по умолчанию | `x-ai/grok-build-0.1` | 19 | 544e22de0a | 13.58 | 27.16 | 3 | н/д | н/д |
| Zhipu AI | Network2 | `z-ai/glm-5.2:network2` | 21 | 9dbbf29544 | 8.47 | 29.72 | 2 | — | да |
| OpenAI | Network2 | `openai/gpt-5.6-luna:network2` | 28 | ef0767bf73 | 5.15 | 30.89 | 0.52 | да | да |
| Zhipu AI | Cxbc · по умолчанию | `z-ai/glm-5.3-flash` | 18 | c8191565cb | 9.51 | 31.7 | 0.95 | — | да |
| Zhipu AI | Cxmc | `z-ai/glm-5.3-flash:cxmc` | 23 | a9d01e4647 | 9.51 | 31.7 | 0.95 | — | да |
| Zhipu AI | Cxz | `z-ai/glm-5.3-flash:cxz` | 22 | 5adf403757 | 9.51 | 31.7 | 0.95 | — | да |
| Zhipu AI | Network | `z-ai/glm-5.3-flash:network` | 26 | b75c1396b2 | 9.9 | 33 | 2 | — | да |
| Xiaomi | Network · по умолчанию | `xiaomi/mimo-v2.5-pro` | 20 | fb4e29b6cf | 18 | 35 | 0.15 | да | да |
| Alibaba (Qwen) | Network · по умолчанию | `qwen/qwen3.7-plus` | 17 | a683b10822 | 9.06 | 36.2 | 0 | да | да |
| DeepSeek | Cxa | `deepseek/deepseek-v4-flash-0731:cxa` | 35 | 84e154c067 | 12.59 | 37.76 | 1 | да | да |
| Zhipu AI | Cxb | `z-ai/glm-5.3:cxb` | 16 | 59f6bbbca1 | 12.42 | 39.04 | 1 | — | да |
| OpenAI | Network · по умолчанию | `openai/gpt-5.6-terra` | 20 | 0a0e148359 | 6.81 | 40.85 | 0.68 | да | да |
| OpenAI | Sub5plus | `openai/gpt-5.6-terra:sub5plus` | 29 | 433fb3eae1 | 6.88 | 41.24 | 0.69 | да | да |
| Google | Ag2 | `google/gemini-3.8-flash:ag2` | 27 | 0f8efd5a82 | 9.43 | 47.15 | 0.94 | — | да |
| Google | Network2 | `google/gemini-3.8-flash:network2` | 32 | 99ee2652af | 9.9 | 49.5 | 0.99 | — | да |
| Zhipu AI | Network · по умолчанию | `z-ai/glm-5.3` | 12 | 86f7519040 | 16.56 | 52.05 | 3 | — | да |
| Zhipu AI | Cxz | `z-ai/glm-5.3:cxz` | 16 | d9c1d7f75e | 17.6 | 55.31 | 2 | — | да |
| Alibaba (Qwen) | Cxa · по умолчанию | `qwen/qwen3.8-max` | 16 | a39753503b | 35 | 57 | 4 | да | да |
| DeepSeek | Cxbc · по умолчанию | `deepseek/deepseek-v4-pro-0813` | 29 | c165c56b05 | 19.8 | 57.6 | 2 | да | да |
| DeepSeek | Network | `deepseek/deepseek-v4-pro-0813:network` | 37 | 3cb552f37e | 19.8 | 57.6 | 0.66 | да | да |
| Google | Network | `google/gemini-3.7-flash:network` | 31 | 9fcc918e75 | 11.55 | 57.75 | 1 | — | да |
| OpenAI | Cxb | `openai/gpt-5.6-terra:cxb` | 24 | acb201673e | 10.56 | 63.36 | 1 | да | да |
| OpenAI | Cx | `openai/gpt-5.6-sol` | 18 | 1e78b5e2a1 | 11 | 66 | 1 | да | да |
| OpenAI | Cxb · по умолчанию | `openai/gpt-5.6-sol:cxb` | 22 | 68a79c91a7 | 11 | 66 | 1 | да | да |
| Google | Network · по умолчанию | `google/gemini-3.5-flash` | 23 | 9a7ad9aeb3 | 11.18 | 67.06 | 1 | да | да |
| Google | Ag · по умолчанию | `google/gemini-3.1-pro-preview` | 29 | e584bd6c2d | 11.33 | 67.96 | 1 | да | да |
| Google | Cxb | `google/gemini-3.1-pro-preview:cxb` | 33 | 27d20fd88d | 11.33 | 67.96 | 1 | да | да |
| Google | Network | `google/gemini-3.1-pro-preview:network` | 37 | e6c4778256 | 11.33 | 67.96 | 1 | да | да |
| OpenAI | Network2 | `openai/gpt-5.6-terra:network2` | 29 | f558b8ade1 | 11.4 | 68.6 | 1 | да | да |
| OpenAI | Network | `openai/gpt-5.6-sol:network` | 26 | 8f276448c5 | 11 | 69 | 1 | да | да |
| MiniMax | Network | `minimax/minimax-m3:network` | 26 | ca44ea7d4b | 23.5 | 70.5 | 5 | да | да |
| MiniMax | Cxbc · по умолчанию | `minimax/minimax-m3` | 18 | 2bef22f97f | 18.86 | 75.43 | 2 | да | да |
| OpenAI | Deepinfra · по умолчанию | `openai/gpt-oss-120b` | 19 | 053db7544f | 37 | 78 | — | да | да |
| Anthropic | Cxc · по умолчанию | `anthropic/claude-haiku-4.5` | 26 | 3029438c1e | 16.35 | 81.72 | 2 | да | — |
| OpenAI | Sub5plus | `openai/gpt-5.6-sol:sub5plus` | 27 | 29a5b7fdaa | 13.84 | 82.96 | 1 | да | да |
| OpenAI | Network2 | `openai/gpt-5.6-sol:network2` | 27 | 4536ff9b00 | 17 | 103 | 2 | да | да |
| Zhipu AI | Network2 | `z-ai/glm-5.3:network2` | 21 | 5a13e27022 | 33.12 | 104.1 | 3 | — | да |
| Другие | Nexus · по умолчанию | `perplexity/sonar` | 16 | f530ed084f | 104.53 | 104.53 | — | — | — |
| DeepSeek | Cxa | `deepseek/deepseek-v4-pro-0813:cxa` | 33 | 140e1a0b38 | 37.34 | 112.02 | 4 | да | да |
| Google | Network · по умолчанию | `google/gemini-3.1-flash-lite` | 28 | 567e884dfe | 19.64 | 117.83 | 2 | да | — |
| Zhipu AI | Network · по умолчанию | `glm-5.1` | 7 | 58bae733f9 | 37.17 | 123.34 | 9 | — | да |
| Moonshot | Cxbc · по умолчанию | `moonshotai/kimi-k3` | 18 | 1adc35c63b | 26 | 130 | 3 | да | да |
| Moonshot | Cxb | `moonshotai/kimi-k3:cxb` | 22 | 3e59a4fa08 | 26 | 130 | 3 | да | да |
| Moonshot | Cxa | `moonshotai/kimi-k3:cxa` | 22 | dee2f25c88 | 26 | 130 | 3 | да | да |
| Anthropic | Sub5max | `anthropic/claude-haiku-4.5:sub5max` | 34 | bfd3f01d07 | 30 | 144 | 3 | да | — |
| Moonshot | Cxa · по умолчанию | `moonshotai/kimi-k2.7-code` | 25 | c138303767 | 34 | 163 | 3 | да | да |
| Google | Ag2 | `google/gemini-3.7-flash:ag2` | 27 | cd2b7a39ba | 34.1 | 170.5 | 3 | — | да |
| Anthropic | Cxb · по умолчанию | `claude-opus-4.6` | 15 | 95b0e3e5bc | 37.72 | 188.58 | 4 | да | да |
| Anthropic | Cxb · по умолчанию | `claude-opus-4.7` | 15 | 1c74c803e3 | 37.72 | 188.58 | 4 | да | да |
| Anthropic | Network | `anthropic/claude-sonnet-5:network` | 33 | bd8f327977 | 44 | 220 | 4 | да | да |
| Anthropic | Cxc · по умолчанию | `anthropic/claude-sonnet-5` | 25 | 395dd451ac | 49.03 | 245.15 | 5 | да | да |
| Alibaba (Qwen) | Nexus · по умолчанию | `qwen/qwen3.6-plus` | 17 | 68ebbf71e5 | 41.47 | 251.61 | — | да | да |
| Moonshot | Network2 | `moonshotai/kimi-k3:network2` | 27 | 87c4f5b20a | 55 | 275 | 6 | да | да |
| Anthropic | Sub5max | `anthropic/claude-sonnet-5:sub5max` | 33 | 8cec538bac | 64 | 314 | 6 | да | да |
| OpenAI | Cx · по умолчанию | `gpt-6-astra` | 11 | bfb342f6d7 | 62.86 | 314.29 | 6 | — | да |
| OpenAI | Cxb | `gpt-6-astra:cxb` | 15 | fd679d46c6 | 62.86 | 314.29 | 6 | — | да |
| Moonshot | Network | `moonshotai/kimi-k3:network` | 26 | dfaf3d65f2 | 63.36 | 316.8 | 6 | да | да |
| Anthropic | Cxc2 | `anthropic/claude-sonnet-5:cxc2` | 30 | 8beabb0deb | 78 | 387 | 8 | да | да |
| Anthropic | Cxc · по умолчанию | `anthropic/claude-opus-4.8` | 25 | ac41913a25 | 81.72 | 408.58 | 8 | да | да |
| Anthropic | Cxc · по умолчанию | `anthropic/claude-opus-5` | 23 | 0338e473bb | 81.72 | 408.58 | 8 | да | да |
| Alibaba (Qwen) | Cxmc · по умолчанию | `qwen/qwen3.6-max-preview` | 24 | 28b7d7d5bb | 81.72 | 490.29 | 8 | да | да |
| Anthropic | Network | `anthropic/claude-opus-5:network` | 31 | c64aadfbae | 99 | 495 | 10 | да | да |
| Anthropic | Cxc2 | `anthropic/claude-opus-5:cxc2` | 28 | 94d052d609 | 129 | 645 | 13 | да | да |
| Anthropic | Sub5max | `anthropic/claude-opus-5:sub5max` | 31 | 9db22dfaf7 | 151 | 750 | 15 | да | да |
| Anthropic | Sub5max | `anthropic/claude-opus-4.8:sub5max` | 33 | dd633e0f75 | 151.99 | 758.7 | 15 | да | да |
| Anthropic | Cxc · по умолчанию | `claude-fable-5-1` | 16 | 12cf822938 | 163.43 | 817.15 | 4 | да | да |
| Другие | Nexus · по умолчанию | `perplexity/sonar-reasoning-pro` | 30 | bc6938f3cc | 209.44 | 835.52 | — | — | да |
| Anthropic | Sub5max | `claude-fable-5-1:sub5max` | 24 | dd06652105 | 252 | 1258 | 25 | да | да |
| Другие | Nexus · по умолчанию | `perplexity/sonar-pro` | 20 | d52787724c | 313.6 | 1568 | — | — | — |
