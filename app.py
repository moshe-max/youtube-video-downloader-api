// ================================
// 🎥 YT DOWNLOADER v5.7 - MIME EMAIL DOWNLOAD FIX
// Handles yt-dlp MIME email format → Extracts MP4 attachment
// ================================

const API_BASE_URL = 'https://yt-downloader-api-2rhl.onrender.com';
const MAX_DURATION_MINUTES = 20;
const MAX_ATTACHMENT_MB = 25;
const DEFAULT_RESOLUTION = '360p';

// ================================
// 🚀 MAIN FUNCTION
// ================================

function processYtEmails() {
  console.log('🔍 Scanning EXACT "yt" emails...');
  
  if (!testApiHealth()) {
    console.log('💥 API DOWN - Skipping');
    return { processed: 0, success: 0, skipped: 0, failed: 0 };
  }
  
  try {
    const searchQuery = 'subject:"yt" -in:trash -label:yt-processed';
    const threads = GmailApp.search(searchQuery, 0, 20);
    console.log(`📧 Found ${threads.length} EXACT "yt" threads`);
    
    let processed = 0, success = 0, skipped = 0, failed = 0;
    const results = [];
    
    let processedLabel = GmailApp.getUserLabelByName('yt-processed') || GmailApp.createLabel('yt-processed');
    
    threads.forEach((thread, threadIndex) => {
      try {
        const threadLabels = thread.getLabels().map(l => l.getName());
        if (threadLabels.includes('yt-processed')) return;
        
        console.log(`\n📧 Thread ${threadIndex + 1}: "${thread.getFirstMessageSubject()}"`);
        
        const messages = thread.getMessages();
        let threadHasUrls = false;
        
        messages.forEach((message, msgIndex) => {
          const urls = extractYouTubeUrls(message.getBody());
          console.log(`  📧 Msg ${msgIndex + 1}: ${urls.length} URLs`);
          
          if (urls.length === 0) return;
          
          threadHasUrls = true;
          
          urls.forEach((url, urlIndex) => {
            try {
              console.log(`    ⬇️ [${urlIndex + 1}/${urls.length}] ${url}`);
              const result = downloadAndReply(message, url);
              results.push(result);
              
              if (result.success) success++;
              else if (result.skipped) skipped++;
              else failed++;
              
              processed++;
              Utilities.sleep(5000);
              
            } catch (e) {
              console.error(`    💥 CRASH: ${e}`);
              failed++;
              processed++;
            }
          });
        });
        
        if (threadHasUrls) {
          thread.addLabel(processedLabel);
          console.log(`  ✅ THREAD MARKED (${processed} URLs)`);
        }
        
      } catch (e) {
        console.error(`❌ Thread ${threadIndex + 1}:`, e);
      }
    });
    
    console.log(`\n📊 SUMMARY: ✅${success} ⏭️${skipped} ❌${failed} (${processed} total)`);
    if (success + failed + skipped > 0) sendSummaryEmail(success, skipped, failed, results);
    
  } catch (error) {
    console.error('💥 CRITICAL:', error);
    sendAdminAlert('PROCESSOR CRASHED', error.toString());
  }
}

// ================================
// 🔍 API HEALTH
// ================================

function testApiHealth() {
  try {
    const response = UrlFetchApp.fetch(`${API_BASE_URL}/info?url=${encodeURIComponent('https://www.youtube.com/watch?v=dQw4w9WgXcQ')}`, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      console.log(`✅ API HEALTHY: ${data.title}`);
      return data.success;
    }
    return false;
  } catch (e) {
    console.log(`❌ API HEALTH CHECK FAILED: ${e}`);
    return false;
  }
}

// ================================
// 🎥 DOWNLOAD + MIME PARSING
// ================================

function downloadAndReply(message, videoUrl) {
  const sender = extractEmail(message.getFrom());
  
  try {
    // 1. Get video info
    const info = getVideoInfo(videoUrl);
    console.log(`  ✅ ${info.title.substring(0, 40)}... (${info.duration})`);
    
    // 2. Duration check
    if (info.length > MAX_DURATION_MINUTES * 60) {
      const reason = `Too long (${formatDuration(info.length)})`;
      replyToSender(message, info, { skipped: true, reason });
      return { success: false, skipped: true, reason, info, sender, url: videoUrl };
    }
    
    // 3. Download + Parse MIME
    console.log(`  ⬇️ Downloading ${DEFAULT_RESOLUTION}...`);
    const mimeBlob = downloadVideoMIME(videoUrl);
    const videoBlob = parseMIMEVideo(mimeBlob, info.title);
    
    const fileSizeMB = videoBlob.getBytes().length / (1024 * 1024);
    const fileName = `${info.title.substring(0, 50)} [${DEFAULT_RESOLUTION}].mp4`;
    videoBlob.setName(fileName);
    
    console.log(`  📁 ${fileName} (${fileSizeMB.toFixed(1)}MB)`);
    
    // 4. Deliver
    if (fileSizeMB <= MAX_ATTACHMENT_MB) {
      console.log(`  📎 ATTACHING`);
      replyToSender(message, info, { method: 'attachment', sizeMB: fileSizeMB.toFixed(1) }, videoBlob);
      return { success: true, method: 'attachment', sizeMB: fileSizeMB.toFixed(1), info, sender, url: videoUrl };
    } else {
      console.log(`  💾 DRIVE`);
      const file = DriveApp.createFile(videoBlob);
      setPrivateSharing(file, sender);
      replyToSender(message, info, { method: 'drive', driveUrl: file.getUrl(), sizeMB: fileSizeMB.toFixed(1) }, null, file);
      return { success: true, method: 'drive', sizeMB: fileSizeMB.toFixed(1), info, sender, url: videoUrl };
    }
    
  } catch (error) {
    console.log(`  ❌ FAILED: ${error.message}`);
    replyToSender(message, null, { error: error.message, videoUrl });
    return { success: false, error: error.message, sender, url: videoUrl };
  }
}

/**
 * 🔥 CRITICAL FIX: Download MIME email → Extract MP4 attachment
 */
function downloadVideoMIME(videoUrl) {
  const response = UrlFetchApp.fetch(`${API_BASE_URL}/download`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
    payload: JSON.stringify({ url: videoUrl, resolution: DEFAULT_RESOLUTION }),
    muteHttpExceptions: true
  });
  
  if (response.getResponseCode() !== 200) {
    throw new Error(`Download HTTP ${response.getResponseCode()}: ${response.getContentText().substring(0, 100)}`);
  }
  
  return response.getBlob().setName('download.eml');
}

/**
 * 🔥 PARSE MIME EMAIL → Extract video attachment
 */
function parseMIMEVideo(mimeBlob, videoTitle) {
  try {
    const content = mimeBlob.getDataAsString();
    
    // Find boundary (e.g., "--=Part_123...")
    const boundaryMatch = content.match(/boundary="([^"]+)"/i) || content.match(/boundary=([^\s\n]+)/i);
    if (!boundaryMatch) {
      throw new Error('No MIME boundary found');
    }
    const boundary = `--${boundaryMatch[1].replace(/-{2,}$/, '')}`;
    
    console.log(`  🔍 MIME boundary: ${boundary}`);
    
    // Split parts by boundary
    const parts = content.split(new RegExp(`${boundary}(?:\\s*--)?`, 'g'));
    
    // Find video attachment (mp4/m4a/webm)
    for (let i = 1; i < parts.length - 1; i++) { // Skip headers
      const part = parts[i].trim();
      
      // Check Content-Type
      if (part.includes('Content-Type:') && 
          (part.includes('video/') || part.includes('audio/'))) {
        
        // Extract filename
        const filenameMatch = part.match(/filename="([^"]+)"/i) || part.match(/filename=([^;\s\n]+)/i);
        const filename = filenameMatch ? filenameMatch[1] : `${videoTitle}.mp4`;
        
        // Find Content-Transfer-Encoding: base64
        if (part.includes('Content-Transfer-Encoding: base64')) {
          // Extract base64 data (after headers, before next boundary)
          const base64Start = part.indexOf('\n\n') + 2;
          const base64End = part.indexOf(boundary, base64Start);
          const base64Data = part.substring(base64Start, base64End).trim()
            .replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, '') // Trim whitespace
            .replace(/\r?\n/g, ''); // Remove line breaks
            
          console.log(`  📎 Found attachment: ${filename} (${base64Data.length} chars)`);
          
          // Decode base64 → video blob
          const bytes = Utilities.base64Decode(base64Data);
          const videoBlob = Utilities.newBlob(bytes, 'video/mp4', filename);
          
          console.log(`  ✅ Video extracted: ${videoBlob.getBytes().length / (1024*1024)}MB`);
          return videoBlob;
        }
      }
    }
    
    throw new Error('No video attachment found in MIME');
    
  } catch (error) {
    console.error('MIME parsing error:', error);
    throw new Error(`MIME parse failed: ${error.message}`);
  }
}

function getVideoInfo(videoUrl) {
  const response = UrlFetchApp.fetch(`${API_BASE_URL}/info?url=${encodeURIComponent(videoUrl)}`, {
    headers: { 'User-Agent': 'Mozilla/5.0' },
    muteHttpExceptions: true
  });
  
  if (response.getResponseCode() !== 200) {
    throw new Error(`Info HTTP ${response.getResponseCode()}`);
  }
  
  const data = JSON.parse(response.getContentText());
  if (!data.success) {
    throw new Error(data.error || 'API error');
  }
  
  data.duration = formatDuration(data.length);
  return data;
}

// ================================
// 📧 REPLIES + UTILITIES
// ================================

function replyToSender(message, info, result, attachment = null, driveFile = null) {
  const senderEmail = extractEmail(message.getFrom());
  const subject = `Re: ${message.getSubject()}`;
  
  let htmlBody;
  
  if (result.skipped) {
    htmlBody = `<h2 style="color:#ff9800">⏭️ SKIPPED</h2><p>${escapeHtml(result.reason)}</p>`;
  } else if (result.error) {
    htmlBody = `<h2 style="color:#f44336">❌ FAILED</h2><p>${escapeHtml(result.error)}</p>`;
  } else if (result.method === 'attachment') {
    htmlBody = `
      <div style="font-family:Arial;max-width:600px">
        <h1 style="color:#4CAF50">✅ VIDEO ATTACHED!</h1>
        <div style="background:#e8f5e8;padding:20px;border-radius:10px">
          <h2>${escapeHtml(info.title)}</h2>
          <p>📎 ${attachment.getName()} (${result.sizeMB}MB)</p>
        </div>
        <img src="${info.thumbnail}" style="max-width:400px;border-radius:10px">
        <p>👤 ${escapeHtml(info.author)} • ⏱️ ${info.duration}</p>
      </div>
    `;
    MailApp.sendEmail(senderEmail, subject, 'Video attached!', { 
      htmlBody, 
      attachments: [attachment] 
    });
    return;
  } else {
    htmlBody = `
      <div style="font-family:Arial;max-width:600px">
        <h1 style="color:#2196F3">💾 DRIVE LINK</h1>
        <div style="background:#e3f2fd;padding:20px;border-radius:10px">
          <h2>${escapeHtml(info.title)}</h2>
          <p>📁 ${driveFile.getName()} (${result.sizeMB}MB)</p>
        </div>
        <a href="${result.driveUrl}" style="background:#2196F3;color:white;padding:15px 30px;
           text-decoration:none;border-radius:25px;display:inline-block">📁 Open Drive</a>
        <img src="${info.thumbnail}" style="max-width:400px;border-radius:10px">
      </div>
    `;
  }
  
  MailApp.sendEmail(senderEmail, subject, result.error || 'Video ready', { htmlBody });
}

function extractYouTubeUrls(body) {
  const text = body.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');
  const urls = new Set();
  
  const patterns = [
    /https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/gi,
    /https?:\/\/(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/gi,
    /youtu\.be\/([a-zA-Z0-9_-]{11})/gi
  ];
  
  patterns.forEach(pattern => {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      urls.add(`https://www.youtube.com/watch?v=${match[1]}`);
    }
  });
  
  return Array.from(urls);
}

function extractEmail(from) {
  const match = from.match(/<(.+?)>/);
  return match ? match[1] : from.split(' ').pop().replace(/[^\w@.-]+/g, '');
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return (text || '').toString().replace(/[&<>"']/g, m => map[m]);
}

function setPrivateSharing(file, email) {
  try {
    file.setSharing(DriveApp.Access.PRIVATE, DriveApp.Permission.VIEW);
    if (email && email !== Session.getActiveUser().getEmail()) {
      file.addViewer(email);
    }
  } catch (e) {}
}

// ================================
// 📧 SUMMARY
// ================================

function sendSummaryEmail(success, skipped, failed, results) {
  let html = `<h2>📊 YT Summary</h2><p><strong>${success}✅ ${skipped}⏭️ ${failed}❌</strong></p>`;
  
  if (success > 0) html += `<h3>✅ Success</h3><ul>${results.filter(r=>r.success).map(r=>`<li>${escapeHtml(r.info?.title||'Unknown')} (${r.method})</li>`).join('')}</ul>`;
  if (failed > 0) html += `<h3 style="color:#f44336">❌ Failed</h3><ul>${results.filter(r=>!r.success&&!r.skipped).map(r=>`<li>${escapeHtml(r.url)}: ${r.error}</li>`).join('')}</ul>`;
  
  MailApp.sendEmail({
    to: Session.getActiveUser().getEmail(),
    subject: `YT: ${success}/${success+skipped+failed}`,
    htmlBody: html
  });
}

// ================================
// 🧪 TESTS
// ================================

function quickSetup() {
  console.log('🔧 Setup...');
  try { GmailApp.createLabel('yt-processed'); } catch(e) {}
  setupHourlyTrigger();
  testWithExactYtEmail();
  console.log('✅ Setup complete!');
}

function setupHourlyTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'processYtEmails') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('processYtEmails').timeBased().everyHours(1).create();
}

function testWithExactYtEmail() {
  GmailApp.sendEmail(
    Session.getActiveUser().getEmail(),
    'yt',
    'Test: https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    { htmlBody: 'Test: <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Rickroll</a>' }
  );
  console.log('✅ Test email sent → Run processYtEmails()');
}

function testSingleDownload() {
  console.log('🧪 Testing SINGLE download...');
  const url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
  
  try {
    const info = getVideoInfo(url);
    console.log(`✅ Info: ${info.title} (${info.duration})`);
    
    const mimeBlob = downloadVideoMIME(url);
    console.log(`✅ MIME: ${mimeBlob.getBytes().length} bytes`);
    
    const videoBlob = parseMIMEVideo(mimeBlob, info.title);
    console.log(`✅ VIDEO: ${videoBlob.getName()} (${(videoBlob.getBytes().length/(1024*1024)).toFixed(1)}MB)`);
    
    // Save to Drive for verification
    const file = DriveApp.createFile(videoBlob);
    console.log(`✅ SAVED: ${file.getUrl()}`);
    
    console.log('🎉 DOWNLOAD SUCCESS!');
  } catch (e) {
    console.error('❌ DOWNLOAD FAILED:', e);
  }
}
