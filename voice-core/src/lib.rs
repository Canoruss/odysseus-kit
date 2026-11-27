use std::ffi::c_void;

/// Decide the next recording state from the current microphone amplitude.
fn voice_state(amplitude: i32, spoke: bool, silence_since: i64, now: i64, started: i64) -> i32 {
    if amplitude > 1800 {
        1 // speech detected, clear silence timer
    } else if spoke {
        if silence_since == 0 {
            2 // begin silence timer
        } else if now.saturating_sub(silence_since) > 1300 {
            3 // send recording
        } else {
            0
        }
    } else if now.saturating_sub(started) > 8000 {
        4 // no speech detected
    } else {
        0
    }
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_Voice_nativeVoiceState(
    _env: *mut c_void, _class: *mut c_void, amplitude: i32, spoke: u8,
    silence_since: i64, now: i64, started: i64,
) -> i32 {
    voice_state(amplitude, spoke != 0, silence_since, now, started)
}

#[cfg(test)]
mod tests {
    use super::voice_state;
    #[test]
    fn recording_lifecycle() {
        assert_eq!(voice_state(2500, false, 0, 1000, 0), 1);
        assert_eq!(voice_state(0, true, 0, 1200, 0), 2);
        assert_eq!(voice_state(0, true, 1200, 2500, 0), 0);
        assert_eq!(voice_state(0, true, 1200, 2501, 0), 3);
        assert_eq!(voice_state(0, false, 0, 8001, 0), 4);
    }
}

use base64::{engine::general_purpose::STANDARD, Engine};
use jni::{objects::{JByteArray, JClass, JString}, sys::jstring, JNIEnv};
use serde_json::json;

fn transcription_body(audio: &[u8], language: &str) -> String {
    json!({"audio": STANDARD.encode(audio), "mime": "audio/mp4", "lang": language}).to_string()
}

/// Construct the private transcription request on the native side.
#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_Voice_nativeTranscriptionBody(
    mut env: JNIEnv, _class: JClass, audio: JByteArray, language: JString,
) -> jstring {
    let result = (|| -> jni::errors::Result<jstring> {
        let bytes = env.convert_byte_array(audio)?;
        let lang: String = env.get_string(&language)?.into();
        Ok(env.new_string(transcription_body(&bytes, &lang))?.into_raw())
    })();
    match result {
        Ok(value) => value,
        Err(_) => {
            let _ = env.throw_new("java/lang/IllegalStateException", "Não foi possível preparar o áudio");
            std::ptr::null_mut()
        }
    }
}

#[cfg(test)]
mod request_tests {
    use super::transcription_body;
    use serde_json::json;
    #[test]
    fn preserves_audio_and_language() {
        let body: serde_json::Value = serde_json::from_str(&transcription_body(&[0, 1, 254, 255], "pt-PT")).unwrap();
        assert_eq!(body, json!({"audio":"AAH+/w==", "mime":"audio/mp4", "lang":"pt-PT"}));
    }
}

fn is_quiet(enabled: bool, minutes: i32) -> bool {
    enabled && (minutes >= 18 * 60 + 30 || minutes < 9 * 60 + 30)
}

fn health_title(title: &str) -> bool {
    let text = title.to_lowercase();
    ["glicose", "insulina", "consulta", "hipoglic"].iter().any(|word| text.contains(word))
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AppSettings_nativeQuiet(
    _env: JNIEnv, _class: JClass, enabled: u8, minutes: i32,
) -> u8 {
    u8::from(is_quiet(enabled != 0, minutes))
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AppSettings_nativeHealthTitle(
    mut env: JNIEnv, _class: JClass, title: JString,
) -> u8 {
    if title.is_null() { return 0; }
    match env.get_string(&title) {
        Ok(text) => u8::from(health_title(&String::from(text))),
        Err(_) => 0,
    }
}

#[cfg(test)]
mod settings_tests {
    use super::{health_title, is_quiet};
    #[test]
    fn quiet_hours_boundaries_and_setting() {
        assert!(!is_quiet(true, 9 * 60 + 30));
        assert!(!is_quiet(true, 18 * 60 + 29));
        assert!(is_quiet(true, 18 * 60 + 30));
        assert!(is_quiet(true, 9 * 60 + 29));
        assert!(!is_quiet(false, 0));
    }
    #[test]
    fn health_reminders() {
        assert!(health_title("Consulta de rotina"));
        assert!(health_title("Hipoglicemia"));
        assert!(!health_title("Tarefa"));
    }
}

const NOTE_TODAY: i32 = 1;
const NOTE_UPCOMING: i32 = 2;
const NOTE_SHOW: i32 = 4;
const NOTE_SCHEDULE: i32 = 8;

fn classify_note(due: i64, now: i64, day_start: i64, day_end: i64) -> i32 {
    let mut result = 0;
    if due >= day_start && due < day_end { result |= NOTE_TODAY; }
    if due >= now - 3_600_000 { result |= NOTE_UPCOMING; }
    if due >= 0 && due >= now - 6 * 3_600_000 {
        if due <= now + 30_000 { result |= NOTE_SHOW; }
        else { result |= NOTE_SCHEDULE; }
    }
    result
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_NoteSync_nativeClassifyNote(
    _env: JNIEnv, _class: JClass, due: i64, now: i64, day_start: i64, day_end: i64,
) -> i32 {
    classify_note(due, now, day_start, day_end)
}

#[cfg(test)]
mod note_tests {
    use super::*;
    #[test]
    fn classifies_scheduled_due_and_stale_notes() {
        let now = 50_000_000;
        let start = now - 10_000;
        let end = now + 86_400_000;
        assert_eq!(classify_note(now + 30_001, now, start, end), NOTE_TODAY | NOTE_UPCOMING | NOTE_SCHEDULE);
        assert_eq!(classify_note(now + 30_000, now, start, end), NOTE_TODAY | NOTE_UPCOMING | NOTE_SHOW);
        assert_eq!(classify_note(now - 6 * 3_600_000 - 1, now, start, end), 0);
        assert_eq!(classify_note(-1, now, start, end), 0);
        assert_eq!(classify_note(end, now, start, end), NOTE_UPCOMING | NOTE_SCHEDULE);
    }
}

fn chat_preview(json_text: &str) -> String {
    let Ok(root) = serde_json::from_str::<serde_json::Value>(json_text) else { return String::new() };
    let Some(history) = root.get("history").and_then(|v| v.as_array())
        .or_else(|| root.get("messages").and_then(|v| v.as_array())) else { return String::new() };
    let Some(message) = history.iter().rev().find(|m| m.get("role").and_then(|v| v.as_str()) == Some("assistant")) else { return String::new() };
    let text = match message.get("content") {
        Some(serde_json::Value::String(text)) => text.clone(),
        Some(content) => content.to_string(),
        None => "null".to_string(),
    };
    let mut cleaned = String::new();
    let mut whitespace = false;
    for line in text.split('\n') {
        if line.trim().starts_with('>') && line.contains('🔧') { continue; }
        for ch in line.chars().chain(std::iter::once('\n')) {
            if "#*`>_".contains(ch) { continue; }
            if ch.is_ascii_whitespace() {
                whitespace = !cleaned.is_empty();
            } else {
                if whitespace { cleaned.push(' '); }
                whitespace = false;
                cleaned.push(ch);
            }
        }
    }
    let mut end = cleaned.len();
    let mut units = 0;
    for (index, ch) in cleaned.char_indices() {
        if units + ch.len_utf16() > 300 { end = index; break; }
        units += ch.len_utf16();
    }
    if end < cleaned.len() { cleaned.truncate(end); cleaned.push('…'); }
    cleaned
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_SyncService_nativeChatPreview(
    mut env: JNIEnv, _class: JClass, body: JString,
) -> jstring {
    let result = (|| -> jni::errors::Result<jstring> {
        let body: String = env.get_string(&body)?.into();
        Ok(env.new_string(chat_preview(&body))?.into_raw())
    })();
    match result {
        Ok(value) => value,
        Err(_) => {
            let _ = env.throw_new("java/lang/IllegalStateException", "Não foi possível ler a resposta");
            std::ptr::null_mut()
        }
    }
}

#[cfg(test)]
mod chat_tests {
    use super::chat_preview;
    #[test]
    fn selects_latest_assistant_and_removes_tool_lines() {
        let input = r##"{"history":[{"role":"assistant","content":"Antiga"},{"role":"assistant","content":"# Olá\n> 🔧 Bash comando\n**Tudo** bem"}]}"##;
        assert_eq!(chat_preview(input), "Olá Tudo bem");
        assert_eq!(chat_preview(r#"{"messages":[{"role":"user","content":"Olá"}]}"#), "");
        assert_eq!(chat_preview("inválido"), "");
        assert_eq!(chat_preview(&format!("{{\"messages\":[{{\"role\":\"assistant\",\"content\":\"{}\"}}]}}", "a".repeat(301))), format!("{}…", "a".repeat(300)));
    }
}

fn agent_tool(name: &str) -> i32 {
    match name {
        "call_contact" => 1,
        "send_sms" => 2,
        "open_whatsapp" => 3,
        "set_alarm" => 4,
        "set_timer" => 5,
        "add_calendar_event" => 6,
        "open_app" => 7,
        "toggle_flashlight" => 8,
        "set_volume" => 9,
        _ => 0,
    }
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_PhoneAgent_nativeTool(
    mut env: JNIEnv, _class: JClass, name: JString,
) -> i32 {
    if name.is_null() { return 0; }
    match env.get_string(&name) {
        Ok(value) => agent_tool(&String::from(value)),
        Err(_) => 0,
    }
}

#[cfg(test)]
mod agent_tests {
    use super::agent_tool;
    #[test]
    fn allowed_tools_and_unknown_input() {
        for (index, name) in ["call_contact", "send_sms", "open_whatsapp", "set_alarm", "set_timer", "add_calendar_event", "open_app", "toggle_flashlight", "set_volume"].iter().enumerate() {
            assert_eq!(agent_tool(name), index as i32 + 1);
        }
        assert_eq!(agent_tool("SEND_SMS"), 0);
        assert_eq!(agent_tool(""), 0);
    }
}

use jni::objects::{JObject, JValue};
use jni::sys::jobject;

fn android_clock_action<'local>(
    env: &mut JNIEnv<'local>, context: JObject<'local>, args: JObject<'local>, alarm: bool,
) -> jni::errors::Result<jobject> {
    let field = env.new_string(if alarm { "hour" } else { "seconds" })?;
    let amount = env.call_method(&args, "getInt", "(Ljava/lang/String;)I", &[JValue::Object(&field)])?.i()?;
    let (action, key) = if alarm {
        ("android.intent.action.SET_ALARM", "android.intent.extra.alarm.HOUR")
    } else {
        ("android.intent.action.SET_TIMER", "android.intent.extra.alarm.LENGTH")
    };
    let minutes = if alarm {
        let name = env.new_string("minutes")?;
        env.call_method(&args, "optInt", "(Ljava/lang/String;I)I", &[JValue::Object(&name), JValue::Int(0)])?.i()?
    } else { 0 };
    let message_key = env.new_string("message")?;
    let default_message = env.new_string(if alarm { "Odysseus" } else { "Temporizador" })?;
    let message = env.call_method(&args, "optString", "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;", &[JValue::Object(&message_key), JValue::Object(&default_message)])?.l()?;
    let action = env.new_string(action)?;
    let intent = env.new_object("android/content/Intent", "(Ljava/lang/String;)V", &[JValue::Object(&action)])?;
    let key = env.new_string(key)?;
    env.call_method(&intent, "putExtra", "(Ljava/lang/String;I)Landroid/content/Intent;", &[JValue::Object(&key), JValue::Int(amount)])?;
    if alarm {
        let key = env.new_string("android.intent.extra.alarm.MINUTES")?;
        env.call_method(&intent, "putExtra", "(Ljava/lang/String;I)Landroid/content/Intent;", &[JValue::Object(&key), JValue::Int(minutes)])?;
    }
    let key = env.new_string("android.intent.extra.alarm.MESSAGE")?;
    env.call_method(&intent, "putExtra", "(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;", &[JValue::Object(&key), JValue::Object(&message)])?;
    let key = env.new_string("android.intent.extra.alarm.SKIP_UI")?;
    env.call_method(&intent, "putExtra", "(Ljava/lang/String;Z)Landroid/content/Intent;", &[JValue::Object(&key), JValue::Bool(1)])?;
    env.call_method(&intent, "addFlags", "(I)Landroid/content/Intent;", &[JValue::Int(0x10000000)])?;
    env.call_method(&context, "startActivity", "(Landroid/content/Intent;)V", &[JValue::Object(&intent)])?;
    let response = if alarm { json!({"ok": true, "time": format!("{:02}:{:02}", amount, minutes)}) }
        else { json!({"ok": true, "seconds": amount}) };
    let serialized = env.new_string(response.to_string())?;
    Ok(env.new_object("org/json/JSONObject", "(Ljava/lang/String;)V", &[JValue::Object(&serialized)])?.into_raw())
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_PhoneAgent_nativeClockAction<'local>(
    mut env: JNIEnv<'local>, _class: JClass<'local>, context: JObject<'local>, args: JObject<'local>, alarm: u8,
) -> jobject {
    match android_clock_action(&mut env, context, args, alarm != 0) {
        Ok(value) => value,
        Err(_) => {
            if !env.exception_check().unwrap_or(true) {
                let _ = env.throw_new("java/lang/IllegalStateException", "Não foi possível abrir o relógio");
            }
            std::ptr::null_mut()
        }
    }
}

fn android_device_action<'local>(
    env: &mut JNIEnv<'local>, context: JObject<'local>, args: JObject<'local>, volume: bool,
) -> jni::errors::Result<jobject> {
    let response = if volume {
        let service = env.new_string("audio")?;
        let manager = env.call_method(&context, "getSystemService", "(Ljava/lang/String;)Ljava/lang/Object;", &[JValue::Object(&service)])?.l()?;
        let stream_key = env.new_string("stream")?;
        let default_stream = env.new_string("music")?;
        let stream_obj = env.call_method(&args, "optString", "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;", &[JValue::Object(&stream_key), JValue::Object(&default_stream)])?.l()?;
        let stream: String = env.get_string(&JString::from(stream_obj))?.into();
        let stream_id = match stream.as_str() { "ring" => 2, "alarm" => 4, _ => 3 };
        let max = env.call_method(&manager, "getStreamMaxVolume", "(I)I", &[JValue::Int(stream_id)])?.i()?;
        let key = env.new_string("percent")?;
        let percent = env.call_method(&args, "optInt", "(Ljava/lang/String;I)I", &[JValue::Object(&key), JValue::Int(50)])?.i()?.clamp(0, 100);
        let value = ((percent as f32 / 100.0) * max as f32).round() as i32;
        env.call_method(&manager, "setStreamVolume", "(III)V", &[JValue::Int(stream_id), JValue::Int(value), JValue::Int(0)])?;
        json!({"ok": true, "percent": percent})
    } else {
        let key = env.new_string("enabled")?;
        let enabled = env.call_method(&args, "optBoolean", "(Ljava/lang/String;Z)Z", &[JValue::Object(&key), JValue::Bool(1)])?.z()?;
        let service = env.new_string("camera")?;
        let manager = env.call_method(&context, "getSystemService", "(Ljava/lang/String;)Ljava/lang/Object;", &[JValue::Object(&service)])?.l()?;
        if manager.is_null() {
            json!({"ok": false, "error": "Lanterna indisponível"})
        } else {
            let ids = env.call_method(&manager, "getCameraIdList", "()[Ljava/lang/String;", &[])?.l()?;
            let ids = jni::objects::JObjectArray::from(ids);
            if env.get_array_length(&ids)? == 0 {
                json!({"ok": false, "error": "Lanterna indisponível"})
            } else {
                let id = env.get_object_array_element(&ids, 0)?;
                env.call_method(&manager, "setTorchMode", "(Ljava/lang/String;Z)V", &[JValue::Object(&id), JValue::Bool(u8::from(enabled))])?;
                json!({"ok": true, "enabled": enabled})
            }
        }
    };
    let serialized = env.new_string(response.to_string())?;
    Ok(env.new_object("org/json/JSONObject", "(Ljava/lang/String;)V", &[JValue::Object(&serialized)])?.into_raw())
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_PhoneAgent_nativeDeviceAction<'local>(
    mut env: JNIEnv<'local>, _class: JClass<'local>, context: JObject<'local>, args: JObject<'local>, volume: u8,
) -> jobject {
    match android_device_action(&mut env, context, args, volume != 0) {
        Ok(value) => value,
        Err(_) => {
            if !env.exception_check().unwrap_or(true) {
                let _ = env.throw_new("java/lang/IllegalStateException", "Não foi possível executar a ação");
            }
            std::ptr::null_mut()
        }
    }
}

mod localization;
pub mod policy;
pub mod guard;
