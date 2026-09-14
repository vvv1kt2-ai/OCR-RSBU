# Одна и та же модель у двух провайдеров

## gemini-3.8-flash (наш OCR)

id: len=23 sha1=4f91698118

```json
{
 "id": "google/gemini-3.8-flash",
 "object": "model",
 "owned_by": "polza-ai",
 "name": "Google: Gemini 3.8 Flash",
 "type": "chat",
 "icon_provider_slug": "google",
 "is_fz152_compliant": false,
 "stores_data_in_russia": false,
 "created": 1788365186,
 "architecture": {
  "modality": "text+image+file+audio+video->text",
  "input_modalities": [
   "text",
   "image",
   "video",
   "file",
   "audio"
  ],
  "output_modalities": [
   "text"
  ],
  "tokenizer": "Gemini",
  "instruct_type": null
 },
 "top_provider": {
  "name": "google-vertex/global/flex",
  "icon_provider_slug": null,
  "is_fz152_compliant": false,
  "stores_data_in_russia": false,
  "is_hosted_on_polza_infrastructure": false,
  "is_moderated": false,
  "context_length": 1048576,
  "max_completion_tokens": 65536,
  "pricing": {
   "prompt_per_million": "44.22075000",
   "completion_per_million": "221.10375000",
   "image_input_per_million": "44.22075000",
   "audio_per_million": "44.22075000",
   "web_search_per_thousand": "1650.90800000",
   "internal_reasoning_per_million": "221.10375000",
   "input_cache_read_per_million": "4.42207500",
   "input_cache_write_per_million": "2.45670833",
   "input_audio_cache_per_
```

## gemini-2.5-flash-lite (наш детектор)

id: len=28 sha1=3ed9437314

```json
{
 "id": "google/gemini-2.5-flash-lite",
 "object": "model",
 "owned_by": "polza-ai",
 "name": "Google: Gemini 2.5 Flash Lite",
 "type": "chat",
 "icon_provider_slug": "google",
 "is_fz152_compliant": false,
 "stores_data_in_russia": false,
 "created": 1769617392,
 "architecture": {
  "modality": "text+image+file+audio+video->text",
  "input_modalities": [
   "text",
   "image",
   "file",
   "audio",
   "video"
  ],
  "output_modalities": [
   "text"
  ],
  "tokenizer": "Gemini",
  "instruct_type": null
 },
 "top_provider": {
  "name": "google-vertex",
  "icon_provider_slug": "google",
  "is_fz152_compliant": false,
  "stores_data_in_russia": false,
  "is_hosted_on_polza_infrastructure": false,
  "is_moderated": false,
  "context_length": 1048576,
  "max_completion_tokens": 65535,
  "pricing": {
   "prompt_per_million": "11.79220000",
   "completion_per_million": "47.16880000",
   "image_input_per_million": "11.79220000",
   "audio_per_million": "35.37660000",
   "web_search_per_thousand": "1650.90800000",
   "internal_reasoning_per_million": "47.16880000",
   "input_cache_read_per_million": "1.17922000",
   "input_cache_write_per_million": "9.82683333",
   "input_audio_cache_per_
```

## эскалатор (наш второй)

id: len=25 sha1=395dd451ac

```json
{
 "id": "anthropic/claude-sonnet-5",
 "object": "model",
 "owned_by": "polza-ai",
 "name": "Anthropic: Claude Sonnet 5",
 "type": "chat",
 "icon_provider_slug": "anthropic",
 "is_fz152_compliant": false,
 "stores_data_in_russia": false,
 "created": 1782846373,
 "architecture": {
  "modality": "text+image+file->text",
  "input_modalities": [
   "text",
   "image",
   "file"
  ],
  "output_modalities": [
   "text"
  ],
  "tokenizer": "Claude",
  "instruct_type": null
 },
 "top_provider": {
  "name": "anthropic",
  "icon_provider_slug": "anthropic",
  "is_fz152_compliant": false,
  "stores_data_in_russia": false,
  "is_hosted_on_polza_infrastructure": false,
  "is_moderated": false,
  "context_length": 1000000,
  "max_completion_tokens": 128000,
  "pricing": {
   "prompt_per_million": "235.84400000",
   "completion_per_million": "1179.22000000",
   "web_search_per_thousand": "1179.22000000",
   "input_cache_read_per_million": "23.58440000",
   "input_cache_write_per_million": "294.80500000",
   "currency": "RUB"
  },
  "supported_parameters": [
   "max_tokens",
   "stop",
   "reasoning",
   "include_reasoning",
   "tools",
   "tool_choice",
   "structured_outputs",
   "response_forma
```


## PlusVibe — все варианты тех же моделей


### эскалатор (наш второй)

| вариант | addressAs | вход ₽/1М | выход ₽/1М |
|---|---|---|---|
| Cxc · по умолчанию | `anthropic/claude-sonnet-5` | 49.03 | 245.15 |
| Network | `anthropic/claude-sonnet-5:network` | 44 | 220 |
| Sub5max | `anthropic/claude-sonnet-5:sub5max` | 64 | 314 |
| Cxc2 | `anthropic/claude-sonnet-5:cxc2` | 78 | 387 |

### gemini-3.8-flash (наш OCR)

| вариант | addressAs | вход ₽/1М | выход ₽/1М |
|---|---|---|---|
| Ag · по умолчанию | `google/gemini-3.8-flash` | 3.78 | 18.86 |
| Ag2 | `google/gemini-3.8-flash:ag2` | 9.43 | 47.15 |
| Network | `google/gemini-3.8-flash:network` | 4.72 | 23.58 |
| Network2 | `google/gemini-3.8-flash:network2` | 9.9 | 49.5 |
