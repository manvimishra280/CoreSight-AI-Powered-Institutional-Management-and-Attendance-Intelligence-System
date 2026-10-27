import {
  useEffect,
  useState,
} from 'react';

import {
  Link,
} from 'react-router-dom';

import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';

import { EnrollmentCapture } from '../../components/enrollment/EnrollmentCapture';

import { useAuth } from '../../context/AuthContext';
import { fetchStudentDashboard } from '../../api/dashboard';

import type {
  EnrollmentResult,
  StudentRecord,
} from '../../types';

export default function Enrollment() {
  const {
    user,
  } = useAuth();

  const [
    profile,
    setProfile,
  ] = useState<StudentRecord | null>(null);

  const [
    phase,
    setPhase,
  ] = useState<
    'intro' | 'capturing' | 'done'
  >('intro');

  const [
    result,
    setResult,
  ] = useState<EnrollmentResult | null>(null);

  const [
    error,
    setError,
  ] = useState('');

  useEffect(() => {
    if (!user) return;

    fetchStudentDashboard(user.id)
      .then(setProfile)
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to load student profile.'
        );
      });
  }, [user]);

  if (!user) {
    return null;
  }

  function startEnrollment() {
    setError('');
    setResult(null);
    setPhase('capturing');
  }

  function handleDone(
    enrollmentResult: EnrollmentResult
  ) {
    setResult(enrollmentResult);

    setPhase('done');

    if (
      enrollmentResult.status ===
      'complete'
    ) {
      fetchStudentDashboard(user.id)
        .then(setProfile)
        .catch(() => undefined);
    }
  }

  return (
    <AppLayout
      role="student"
      title="Face Enrollment"
    >
      <div className="max-w-2xl mx-auto space-y-5">

        {/* Header */}

        <div>
          <p className="text-xs text-text-dim uppercase tracking-wider">
            Student Security
          </p>

          <h1 className="font-display text-2xl font-semibold mt-1">
            Face Enrollment
          </h1>

          <p className="text-sm text-text-dim mt-2">
            Your camera samples are processed to create
            the face profile associated with your own
            CoreSight student account.
          </p>
        </div>

        {/* Student identity */}

        <Card className="p-4">

          <div className="grid grid-cols-2 gap-4">

            <div>
              <p className="text-[10px] uppercase tracking-wider text-text-faint">
                Student
              </p>

              <p className="text-sm text-text mt-1">
                {profile?.name || 'Loading…'}
              </p>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider text-text-faint">
                Roll Number
              </p>

              <p className="text-sm text-text mt-1 font-mono">
                {profile?.rollNumber || '—'}
              </p>
            </div>

          </div>

        </Card>

        {error && (
          <Card className="p-4 border-blocked/30">
            <p className="text-xs text-blocked">
              {error}
            </p>
          </Card>
        )}

        {/* Intro */}

        {phase === 'intro' && (
          <Card className="p-6 space-y-5">

            <div>

              <h2 className="font-display font-semibold">
                Before you start
              </h2>

              <p className="text-sm text-text-dim mt-2">
                We will capture multiple valid samples
                from your camera and generate your face
                embedding on the server.
              </p>

            </div>

            <ul className="text-sm text-text-dim space-y-2">
              <li>
                ✓ Use a well-lit environment.
              </li>

              <li>
                ✓ Keep only your face inside the camera frame.
              </li>

              <li>
                ✓ Look towards the camera.
              </li>

              <li>
                ✓ Do not use a photo or another screen.
              </li>

              <li>
                ✓ Keep your face visible during the capture.
              </li>
            </ul>

            <div className="rounded-xl bg-surface-2 border border-border-soft p-4">
              <p className="text-xs text-text-dim">
                Your face embedding will be saved against
                the currently logged-in student account.
              </p>
            </div>

            <Button
              className="w-full"
              onClick={startEnrollment}
            >
              Begin Face Enrollment
            </Button>

            <Link
              to="/student"
              className="block text-center text-xs text-text-dim hover:text-accent"
            >
              ← Back to dashboard
            </Link>

          </Card>
        )}

        {/* Camera */}

        {phase === 'capturing' && (
          <div className="space-y-4">

            <EnrollmentCapture
              studentId={user.id}
              onDone={handleDone}
            />

            <p className="text-[11px] text-text-faint text-center">
              The server verifies each sample before
              accepting it.
            </p>

          </div>
        )}

        {/* Result */}

        {phase === 'done' &&
          result && (
            <Card className="p-6 text-center rise-in">

              {result.status === 'complete' ? (
                <>
                  <p className="text-verified text-4xl">
                    ✓
                  </p>

                  <h2 className="font-display text-lg font-semibold mt-3">
                    Face Enrollment Complete
                  </h2>

                  <p className="text-sm text-text-dim mt-2">
                    Your face profile has been saved
                    for your CoreSight student account.
                  </p>

                  <div className="grid grid-cols-2 gap-3 mt-5">

                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-[10px] text-text-faint uppercase">
                        Samples
                      </p>

                      <p className="font-mono text-lg mt-1">
                        {result.samplesProcessed}
                      </p>
                    </div>

                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-[10px] text-text-faint uppercase">
                        Valid
                      </p>

                      <p className="font-mono text-lg mt-1 text-verified">
                        {result.validSamples}
                      </p>
                    </div>

                  </div>

                  <Link
                    to="/student"
                    className="block mt-5"
                  >
                    <Button className="w-full">
                      Return to Dashboard
                    </Button>
                  </Link>
                </>
              ) : (
                <>
                  <p className="text-blocked text-4xl">
                    !
                  </p>

                  <h2 className="font-display text-lg font-semibold mt-3">
                    Enrollment could not be completed
                  </h2>

                  <p className="text-sm text-text-dim mt-2">
                    {result.reason ||
                      'The required number of valid samples was not collected.'}
                  </p>

                  <Button
                    className="w-full mt-5"
                    onClick={startEnrollment}
                  >
                    Try Again
                  </Button>

                  <Link
                    to="/student"
                    className="block mt-4 text-xs text-text-dim hover:text-accent"
                  >
                    Back to dashboard
                  </Link>
                </>
              )}

            </Card>
          )}

      </div>
    </AppLayout>
  );
}