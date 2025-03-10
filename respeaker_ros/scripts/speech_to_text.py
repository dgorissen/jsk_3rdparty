#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yuki Furuta <furushchev@jsk.imi.i.u-tokyo.ac.jp>

import actionlib
import rospy
try:
    import speech_recognition as SR
except ImportError as e:
    raise ImportError(str(e) + '\nplease try "pip install speechrecognition"')

from actionlib_msgs.msg import GoalStatus, GoalStatusArray
from audio_common_msgs.msg import AudioData
from sound_play.msg import SoundRequest, SoundRequestAction, SoundRequestGoal
from speech_recognition_msgs.msg import SpeechRecognitionCandidates


class SpeechToText(object):
    def __init__(self):
        # format of input audio data
        self.sample_rate = rospy.get_param("~sample_rate", 16000)
        self.sample_width = rospy.get_param("~sample_width", 2)
        # language of STT service
        self.language = rospy.get_param("~language", "en-GB")
        # ignore voice input while the robot is speaking
        self.self_cancellation = rospy.get_param("~self_cancellation", False)
        # time to assume as SPEAKING after tts service is finished
        self.tts_tolerance = rospy.Duration.from_sec(
            rospy.get_param("~tts_tolerance", 1.0))
        tts_action_names = rospy.get_param(
            '~tts_action_names', ['sound_play'])

        self.recognizer = SR.Recognizer()

        self.tts_action = None
        self.last_tts = None
        self.is_canceling = False
        self.tts_actions = []
        if self.self_cancellation:
            for tts_action_name in tts_action_names:
                tts_action = actionlib.SimpleActionClient(
                    tts_action_name, SoundRequestAction)
                if tts_action.wait_for_server(rospy.Duration(5.0)):
                    self.tts_actions.append(tts_action)
                else:
                    rospy.logerr(
                        "action '{}' is not initialized."
                        .format(tts_action_name))
                self.tts_timer = rospy.Timer(rospy.Duration(0.1), self.tts_timer_cb)

        self.pub_speech = rospy.Publisher(
            "speech_to_text", SpeechRecognitionCandidates, queue_size=1)
        self.sub_audio = rospy.Subscriber("speech_audio", AudioData, self.audio_cb)

    def tts_timer_cb(self, event):
        stamp = event.current_real
        active = False
        for tts_action in self.tts_actions:
            for st in tts_action.action_client.last_status_msg.status_list:
                if st.status == GoalStatus.ACTIVE:
                    active = True
                    break
            if active:
                break
        if active:
            if not self.is_canceling:
                rospy.logdebug("START CANCELLATION")
                self.is_canceling = True
                self.last_tts = None
        elif self.is_canceling:
            if self.last_tts is None:
                self.last_tts = stamp
            if stamp - self.last_tts > self.tts_tolerance:
                rospy.logdebug("END CANCELLATION")
                self.is_canceling = False

    def audio_cb(self, msg):
        if self.is_canceling:
            rospy.loginfo("Speech is cancelled")
            return
        data = SR.AudioData(msg.data, self.sample_rate, self.sample_width)
        try:
            rospy.loginfo("Waiting for result %d" % len(data.get_raw_data()))
            result = self.recognizer.recognize_google(
                data, language=self.language)
            msg = SpeechRecognitionCandidates(transcript=[result])
            self.pub_speech.publish(msg)
        except SR.UnknownValueError as e:
            rospy.logerr("Failed to recognize: %s" % str(e))
        except SR.RequestError as e:
            rospy.logerr("Failed to recognize: %s" % str(e))


if __name__ == '__main__':
    rospy.init_node("speech_to_text")
    stt = SpeechToText()
    rospy.spin()
