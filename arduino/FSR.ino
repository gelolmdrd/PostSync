#define NUM_SENSORS 13

// Vibration motor pins (PWM-capable)
int vibrationPins[] = {2, 3, 4, 5};

// Pressure sensor pins
int sensorPins[NUM_SENSORS] = {A0, A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12};

int fsrReading;
float fsrVoltage;
unsigned long fsrResistance;
unsigned long fsrConductance;
float fsrForce;
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
        fsrReading = analogRead(sensorPins[i]);
        fsrVoltage = fsrReading * (5000.0 / 1023.0); // Convert to mV

        if (fsrVoltage == 0)
        {
            fsrForce = 0;
        }
        else
        {
            fsrResistance = (5000 - fsrVoltage) * 10000 / fsrVoltage;
            fsrConductance = 1000000 / fsrResistance;

            if (fsrConductance <= 1000)
            {
                fsrForce = fsrConductance / 80.0;
            }
            else
            {
                fsrForce = (fsrConductance - 1000) / 30.0;
            }
        }

        output += String(fsrForce, 2);
        if (i < NUM_SENSORS - 1)
            output += ",";
    }

    Serial.println(output);
    delay(100);

    // Check for a new trigger signal from NodeMCU
    if (Serial.available())
    {
        String receivedString = Serial.readStringUntil('\n'); // Read until newline
        receivedString.trim();                                // Remove any spaces or extra characters

        if (receivedString == "1" || receivedString == "0")
        {
            command = receivedString[0]; // Assign first character
        }
    }

    unsigned long currentTime = millis();

    // Trigger haptic feedback only when a new "1" is received
    if (command == '1' && !hapticActive && (currentTime - lastHapticTime >= HAPTIC_COOLDOWN))
    {
        hapticActive = true;
        lastHapticTime = currentTime;
        triggerHapticFeedback();
    }

    // Ensure motors are turned off properly
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
