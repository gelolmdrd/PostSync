#define NUM_SENSORS 13

// Vibration motor pins (PWM-capable)
int vibrationPins[] = {2, 3, 4, 5};

// Pressure sensor pins
int sensorPins[NUM_SENSORS] = {A0, A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12};

char command = '0';        // Default to '0' (no vibration)
bool hapticActive = false; // Track whether haptic feedback is active
unsigned long lastHapticTime = 0;
const unsigned long HAPTIC_DURATION = 1000;  // 1 sec duration
const unsigned long HAPTIC_COOLDOWN = 10000; // 10 sec cooldown

void setup()
{
    Serial.begin(9600);
    for (int i = 0; i < 4; i++)
    {
        pinMode(vibrationPins[i], OUTPUT);
        analogWrite(vibrationPins[i], 0);
    }
}

void loop()
{
    // Send sensor data to NodeMCU
    String output = "";
    for (int i = 0; i < NUM_SENSORS; i++)
    {
        int fsrReading = analogRead(sensorPins[i]);
        float fsrVoltage = fsrReading * (5000.0 / 1023.0);
        float fsrForce = (fsrVoltage == 0) ? 0 : fsrVoltage * 10 / 5000.0;
        output += String(fsrForce, 2);
        if (i < NUM_SENSORS - 1)
            output += ",";
    }

    Serial.println(output);
    delay(100);

    // Check for a new trigger signal from Python
    if (Serial.available())
    {
        char newCommand = Serial.read();

        if (newCommand == '1' || newCommand == '0')
        {
            command = newCommand; // Update the command with the latest valid value
        }
    }

    unsigned long currentTime = millis();

    // Handle haptic feedback activation
    if (command == '1' && !hapticActive && (currentTime - lastHapticTime >= HAPTIC_COOLDOWN))
    {
        hapticActive = true;
        lastHapticTime = currentTime;
        triggerHapticFeedback();
    }

    // Handle haptic feedback deactivation
    if (command == '0' && hapticActive)
    {
        stopHapticFeedback();
        hapticActive = false;
    }
}

void triggerHapticFeedback()
{
    for (int i = 0; i < 4; i++)
    {
        analogWrite(vibrationPins[i], 128);
    }
    delay(HAPTIC_DURATION);
    stopHapticFeedback();
}

void stopHapticFeedback()
{
    for (int i = 0; i < 4; i++)
    {
        analogWrite(vibrationPins[i], 0);
    }
}
