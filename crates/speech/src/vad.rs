use crate::config::VadConfig;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VadEvent {
    SpeechStarted,
    SpeechEnded,
}

#[derive(Debug, Clone)]
pub struct EnergyVad {
    config: VadConfig,
    speaking: bool,
    speech_frames: usize,
    silence_ms: u64,
}

impl EnergyVad {
    pub fn new(config: VadConfig) -> Self {
        Self {
            config,
            speaking: false,
            speech_frames: 0,
            silence_ms: 0,
        }
    }

    pub fn accept_pcm16(&mut self, frame: &[u8]) -> Option<VadEvent> {
        let rms = pcm16_rms(frame);
        let is_voice = rms >= self.config.rms_threshold;

        if is_voice {
            self.silence_ms = 0;
            self.speech_frames += 1;
            if !self.speaking && self.speech_frames >= self.config.start_frames {
                self.speaking = true;
                return Some(VadEvent::SpeechStarted);
            }
            return None;
        }

        self.speech_frames = 0;
        if self.speaking {
            self.silence_ms += self.config.frame_ms;
            if self.silence_ms >= self.config.end_silence_ms {
                self.speaking = false;
                self.silence_ms = 0;
                return Some(VadEvent::SpeechEnded);
            }
        }

        None
    }

    pub fn is_speaking(&self) -> bool {
        self.speaking
    }
}

pub fn pcm16_rms(frame: &[u8]) -> f32 {
    let samples = frame.chunks_exact(2);
    let count = samples.len();
    if count == 0 {
        return 0.0;
    }

    let sum = frame
        .chunks_exact(2)
        .map(|bytes| i16::from_le_bytes([bytes[0], bytes[1]]) as f32 / i16::MAX as f32)
        .map(|sample| sample * sample)
        .sum::<f32>();

    (sum / count as f32).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn silent_frame_has_zero_rms() {
        assert_eq!(pcm16_rms(&[0; 320]), 0.0);
    }

    #[test]
    fn detects_start_and_end() {
        let mut vad = EnergyVad::new(VadConfig {
            rms_threshold: 0.01,
            start_frames: 2,
            end_silence_ms: 40,
            frame_ms: 20,
        });
        let voice = vec![0x00, 0x20].repeat(160);
        let silence = vec![0x00, 0x00].repeat(160);

        assert_eq!(vad.accept_pcm16(&voice), None);
        assert_eq!(vad.accept_pcm16(&voice), Some(VadEvent::SpeechStarted));
        assert_eq!(vad.accept_pcm16(&silence), None);
        assert_eq!(vad.accept_pcm16(&silence), Some(VadEvent::SpeechEnded));
    }
}
