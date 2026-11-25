/**
 * White Hole Publisher — backend (Google Apps Script web app).
 *
 * Holds the TikTok client secret and the users' tokens server-side. The browser only
 * receives an opaque session id. Endpoints are called with POST (text/plain JSON body).
 *
 * Script properties required:
 *   TT_CLIENT_KEY, TT_CLIENT_SECRET, ALLOWED_ORIGIN (e.g. https://ch4p3.github.io)
 */
var API = 'https://open.tiktokapis.com/v2';
var REDIRECT_URI = 'https://ch4p3.github.io/WHITE_hOLE_bOT/publisher/callback.html';
var MEDIA_PREFIX = 'https://ch4p3.github.io/WHITE_hOLE_bOT/media/';

function props_() { return PropertiesService.getScriptProperties(); }
function out_(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }

function doGet(e) { return out_({ ok: true, service: 'White Hole Publisher API' }); }

function doPost(e) {
  var body = {};
  try { body = JSON.parse(e.postData.contents || '{}'); } catch (err) { return out_({ ok: false, error: 'bad_json' }); }
  try {
    switch (body.action) {
      case 'token': return out_(exchangeCode_(body.code));
      case 'creator': return out_(creatorInfo_(body.sid));
      case 'post': return out_(post_(body));
      case 'upload_init': return out_(uploadInit_(body));
      case 'draft': return out_(draft_(body));
      case 'status': return out_(status_(body.sid, body.publish_id));
      case 'queue': return out_(queue_(body.sid));
      case 'cancel': return out_(cancel_(body.sid, body.id));
      case 'disconnect': return out_(disconnect_(body.sid));
      default: return out_({ ok: false, error: 'unknown_action' });
    }
  } catch (err) {
    return out_({ ok: false, error: String(err && err.message || err).slice(0, 300) });
  }
}

/* ---------------- sessions & tokens ---------------- */
function session_(sid) {
  if (!sid || !/^[a-f0-9]{32}$/.test(sid)) throw new Error('not_connected');
  var raw = props_().getProperty('s_' + sid);
  if (!raw) throw new Error('not_connected');
  return JSON.parse(raw);
}
function saveSession_(sid, s) { props_().setProperty('s_' + sid, JSON.stringify(s)); }

function exchangeCode_(code) {
  if (!code) throw new Error('missing_code');
  var p = props_();
  var r = UrlFetchApp.fetch(API + '/oauth/token/', {
    method: 'post', muteHttpExceptions: true,
    contentType: 'application/x-www-form-urlencoded',
    payload: { client_key: p.getProperty('TT_CLIENT_KEY'), client_secret: p.getProperty('TT_CLIENT_SECRET'),
               code: code, grant_type: 'authorization_code', redirect_uri: REDIRECT_URI }
  });
  var d = JSON.parse(r.getContentText());
  if (!d.access_token) throw new Error('token_exchange_failed: ' + (d.error_description || d.error || r.getResponseCode()));
  var sid = Utilities.getUuid().replace(/-/g, '');
  saveSession_(sid, { open_id: d.open_id, access: d.access_token, refresh: d.refresh_token,
                      exp: Date.now() + (d.expires_in - 120) * 1000, scope: d.scope });
  return { ok: true, sid: sid, scope: d.scope };
}

function accessToken_(sid) {
  var s = session_(sid);
  if (Date.now() < s.exp) return s.access;
  var p = props_();
  var r = UrlFetchApp.fetch(API + '/oauth/token/', {
    method: 'post', muteHttpExceptions: true, contentType: 'application/x-www-form-urlencoded',
    payload: { client_key: p.getProperty('TT_CLIENT_KEY'), client_secret: p.getProperty('TT_CLIENT_SECRET'),
               grant_type: 'refresh_token', refresh_token: s.refresh }
  });
  var d = JSON.parse(r.getContentText());
  if (!d.access_token) throw new Error('reconnect_required');
  s.access = d.access_token; s.refresh = d.refresh_token || s.refresh; s.exp = Date.now() + (d.expires_in - 120) * 1000;
  saveSession_(sid, s);
  return s.access;
}

function tt_(sid, path, payload) {
  var r = UrlFetchApp.fetch(API + path, {
    method: 'post', muteHttpExceptions: true, contentType: 'application/json; charset=UTF-8',
    headers: { Authorization: 'Bearer ' + accessToken_(sid) }, payload: JSON.stringify(payload || {})
  });
  var d = JSON.parse(r.getContentText() || '{}');
  var code = d.error && d.error.code;
  if (code && code !== 'ok') throw new Error(code + (d.error.message ? ': ' + d.error.message : ''));
  return d.data || {};
}

/* ---------------- TikTok calls ---------------- */
function creatorInfo_(sid) {
  var d = tt_(sid, '/post/publish/creator_info/query/', {});
  return { ok: true, creator: d };
}

function postInfo_(b) {
  var levels = ['PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'FOLLOWER_OF_CREATOR', 'SELF_ONLY'];
  if (levels.indexOf(b.privacy_level) < 0) throw new Error('privacy_required');
  if (b.brand_content_toggle && b.privacy_level === 'SELF_ONLY') throw new Error('branded_content_cannot_be_private');
  return {
    title: String(b.title || '').slice(0, 2200),
    privacy_level: b.privacy_level,
    disable_comment: !b.allow_comment, disable_duet: !b.allow_duet, disable_stitch: !b.allow_stitch,
    brand_content_toggle: !!b.brand_content_toggle, brand_organic_toggle: !!b.brand_organic_toggle
  };
}

function post_(b) {
  var info = postInfo_(b);
  if (!b.consent) throw new Error('consent_required');
  if (String(b.video_url || '').indexOf(MEDIA_PREFIX) !== 0) throw new Error('video_must_be_in_library');
  if (b.schedule_at) {
    var when = new Date(b.schedule_at).getTime();
    if (!(when > Date.now() + 60000)) throw new Error('schedule_must_be_in_future');
    var s = session_(b.sid);
    var q = JSON.parse(props_().getProperty('q_' + b.sid) || '[]');
    var item = { id: Utilities.getUuid().slice(0, 8), when: when, video_url: b.video_url, info: info, state: 'scheduled' };
    q.push(item); props_().setProperty('q_' + b.sid, JSON.stringify(q));
    return { ok: true, scheduled: item };
  }
  var d = tt_(b.sid, '/post/publish/video/init/', { post_info: info, source_info: { source: 'PULL_FROM_URL', video_url: b.video_url } });
  return { ok: true, publish_id: d.publish_id };
}

function draft_(b) {
  if (!b.consent) throw new Error('consent_required');
  if (String(b.video_url || '').indexOf(MEDIA_PREFIX) !== 0) throw new Error('video_must_be_in_library');
  var d = tt_(b.sid, '/post/publish/inbox/video/init/', { source_info: { source: 'PULL_FROM_URL', video_url: b.video_url } });
  return { ok: true, publish_id: d.publish_id };
}

function uploadInit_(b) {
  var info = postInfo_(b);
  if (!b.consent) throw new Error('consent_required');
  var size = Number(b.video_size);
  if (!(size > 0)) throw new Error('bad_size');
  var d = tt_(b.sid, '/post/publish/video/init/', {
    post_info: info, source_info: { source: 'FILE_UPLOAD', video_size: size, chunk_size: size, total_chunk_count: 1 } });
  return { ok: true, publish_id: d.publish_id, upload_url: d.upload_url };
}

function status_(sid, publishId) {
  var d = tt_(sid, '/post/publish/status/fetch/', { publish_id: publishId });
  return { ok: true, status: d };
}

function queue_(sid) {
  session_(sid);
  return { ok: true, queue: JSON.parse(props_().getProperty('q_' + sid) || '[]') };
}

function cancel_(sid, id) {
  session_(sid);
  var q = JSON.parse(props_().getProperty('q_' + sid) || '[]').filter(function (x) { return x.id !== id; });
  props_().setProperty('q_' + sid, JSON.stringify(q));
  return { ok: true };
}

function disconnect_(sid) {
  var s = session_(sid), p = props_();
  try {
    UrlFetchApp.fetch(API + '/oauth/revoke/', { method: 'post', muteHttpExceptions: true,
      contentType: 'application/x-www-form-urlencoded',
      payload: { client_key: p.getProperty('TT_CLIENT_KEY'), client_secret: p.getProperty('TT_CLIENT_SECRET'), token: s.access } });
  } catch (err) {}
  p.deleteProperty('s_' + sid); p.deleteProperty('q_' + sid);
  return { ok: true };
}

/* ---------------- scheduled posts (time trigger every 10 minutes) ---------------- */
function runScheduled() {
  var all = props_().getProperties();
  Object.keys(all).forEach(function (k) {
    if (k.indexOf('q_') !== 0) return;
    var sid = k.slice(2), q = JSON.parse(all[k] || '[]'), changed = false;
    q.forEach(function (item) {
      if (item.state !== 'scheduled' || item.when > Date.now()) return;
      try {
        var d = tt_(sid, '/post/publish/video/init/', { post_info: item.info, source_info: { source: 'PULL_FROM_URL', video_url: item.video_url } });
        item.state = 'sent'; item.publish_id = d.publish_id;
      } catch (err) { item.state = 'failed'; item.error = String(err.message || err).slice(0, 200); }
      changed = true;
    });
    if (changed) props_().setProperty(k, JSON.stringify(q.filter(function (x) { return x.state === 'scheduled' || x.when > Date.now() - 7 * 864e5; })));
  });
}

function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'runScheduled') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('runScheduled').timeBased().everyMinutes(10).create();
}
