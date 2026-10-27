import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { useAuth } from '../../context/AuthContext';
import { fetchStudentDashboard } from '../../api/dashboard';
import type { StudentRecord } from '../../types';

function getAttendanceStatus(percentage: number) {
  if (percentage >= 85) {
    return {
      label: 'Excellent',
      description: 'Your attendance is in a healthy range.',
      color: 'text-verified',
      barColor: 'bg-verified',
    };
  }

  if (percentage >= 75) {
    return {
      label: 'Good',
      description: 'Keep attending classes regularly.',
      color: 'text-accent',
      barColor: 'bg-accent',
    };
  }

  return {
    label: 'Needs attention',
    description: 'Attend upcoming classes regularly to improve attendance.',
    color: 'text-warning',
    barColor: 'bg-warning',
  };
}

function MetricCard({
  label,
  value,
  description,
  icon,
}: {
  label: string;
  value: string;
  description: string;
  icon: string;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-text-dim">
            {label}
          </p>
          <p className="mt-3 font-display text-2xl font-semibold text-text">
            {value}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-text-dim">
            {description}
          </p>
        </div>

        <span
          aria-hidden="true"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-lg"
        >
          {icon}
        </span>
      </div>
    </Card>
  );
}

export default function StudentHome() {
  const { user } = useAuth();

  const [record, setRecord] = useState<StudentRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDashboard = useCallback(async () => {
    if (!user) {
      setLoading(false);
      setError('Please sign in to view your student dashboard.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const studentRecord = await fetchStudentDashboard(user.id);
      setRecord(studentRecord);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load your dashboard. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return (
      <AppLayout role="student" title="Dashboard">
        <div className="mx-auto max-w-7xl space-y-5">
          <div className="animate-pulse space-y-3">
            <div className="h-8 w-64 rounded-lg bg-surface-2" />
            <div className="h-4 w-80 max-w-full rounded bg-surface-2" />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-36 animate-pulse rounded-2xl border border-border-soft bg-surface"
              />
            ))}
          </div>

          <Card className="p-6">
            <p className="text-sm text-text-dim">
              Loading your attendance analytics...
            </p>
          </Card>
        </div>
      </AppLayout>
    );
  }

  if (error || !record) {
    return (
      <AppLayout role="student" title="Dashboard">
        <div className="mx-auto max-w-7xl">
          <Card className="p-6">
            <div className="flex items-start gap-3">
              <span className="text-xl" aria-hidden="true">
                ⚠
              </span>

              <div className="flex-1">
                <h2 className="font-display text-lg font-semibold text-text">
                  Dashboard unavailable
                </h2>

                <p className="mt-2 text-sm text-text-dim">
                  {error || 'Your student record could not be loaded.'}
                </p>

                <button
                  type="button"
                  onClick={() => void loadDashboard()}
                  className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
                >
                  Try again
                </button>
              </div>
            </div>
          </Card>
        </div>
      </AppLayout>
    );
  }

  const attendance = Math.min(
    100,
    Math.max(0, Number(record.overallAttendancePct) || 0),
  );

  const attendanceStatus = getAttendanceStatus(attendance);
  const firstName = record.name?.trim().split(/\s+/)[0] || 'Student';

  return (
    <AppLayout role="student" title="Dashboard">
      <div className="mx-auto max-w-7xl space-y-6 pb-8">
        {/* Welcome section */}
        <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-text-dim">
              Student portal
            </p>

            <h1 className="mt-2 font-display text-2xl font-semibold text-text sm:text-3xl">
              Welcome back, {firstName}!
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-dim">
              Here is an overview of your attendance, student profile and face
              enrollment status.
            </p>
          </div>

          <Link
            to="/student/profile"
            className="inline-flex w-fit items-center justify-center gap-2 rounded-xl border border-border-soft bg-surface px-4 py-2.5 text-sm font-medium text-text transition hover:bg-surface-2"
          >
            View profile
            <span aria-hidden="true">→</span>
          </Link>
        </section>

        {/* Student identity */}
        <Card className="overflow-hidden p-5 sm:p-6">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-surface-2 font-display text-xl font-semibold text-accent">
                {firstName.charAt(0).toUpperCase()}
              </div>

              <div className="min-w-0">
                <h2 className="truncate font-display text-lg font-semibold text-text">
                  {record.name}
                </h2>

                <p className="mt-1 break-all text-sm text-text-dim">
                  {record.email}
                </p>

                <p className="mt-1 text-xs text-text-dim">
                  Roll number: {record.rollNumber || 'Not available'}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 sm:min-w-64">
              <div>
                <p className="text-xs text-text-dim">Department</p>
                <p className="mt-1 text-sm font-medium text-text">
                  {record.department || 'Not assigned'}
                </p>
              </div>

              <div>
                <p className="text-xs text-text-dim">Section</p>
                <p className="mt-1 text-sm font-medium text-text">
                  {record.section || 'Not assigned'}
                </p>
              </div>
            </div>
          </div>
        </Card>

        {/* Analytics heading */}
        <section>
          <div className="mb-4">
            <h2 className="font-display text-lg font-semibold text-text">
              Your analytics
            </h2>
            <p className="mt-1 text-sm text-text-dim">
              A quick summary of your current student record.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Overall attendance"
              value={`${attendance.toFixed(1)}%`}
              description="Your recorded attendance percentage."
              icon="◷"
            />

            <MetricCard
              label="Attendance status"
              value={attendanceStatus.label}
              description={attendanceStatus.description}
              icon="◉"
            />

            <MetricCard
              label="Face enrollment"
              value={record.faceEnrolled ? 'Complete' : 'Pending'}
              description={
                record.faceEnrolled
                  ? 'Your face enrollment is complete.'
                  : 'Complete enrollment to prepare for face-based attendance.'
              }
              icon="◎"
            />

            <MetricCard
              label="Student profile"
              value={
                record.rollNumber && record.department && record.batchId
                  ? 'Available'
                  : 'Review details'
              }
              description="Review your academic and contact information."
              icon="▤"
            />
          </div>
        </section>

        {/* Attendance analytics */}
        <section className="grid grid-cols-1 gap-5 lg:grid-cols-5">
          <Card className="p-5 sm:p-6 lg:col-span-3">
            <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
              <div>
                <h2 className="font-display text-lg font-semibold text-text">
                  Attendance overview
                </h2>
                <p className="mt-1 text-sm text-text-dim">
                  Your overall recorded attendance.
                </p>
              </div>

              <span
                className={`w-fit rounded-full bg-surface-2 px-3 py-1 text-xs font-medium ${attendanceStatus.color}`}
              >
                {attendanceStatus.label}
              </span>
            </div>

            <div className="mt-7 flex items-center gap-5">
              <div className="relative flex h-28 w-28 shrink-0 items-center justify-center rounded-full">
                <svg
                  className="absolute inset-0 h-full w-full -rotate-90"
                  viewBox="0 0 100 100"
                  role="img"
                  aria-label={`Overall attendance ${attendance.toFixed(1)} percent`}
                >
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="9"
                    className="text-surface-2"
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="9"
                    strokeLinecap="round"
                    strokeDasharray={`${(attendance / 100) * 263.89} 263.89`}
                    className={attendanceStatus.color}
                  />
                </svg>

                <div className="text-center">
                  <p className="font-display text-xl font-semibold text-text">
                    {attendance.toFixed(1)}%
                  </p>
                  <p className="text-[10px] text-text-dim">Attendance</p>
                </div>
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text">
                  {attendance >= 75
                    ? 'Keep up the good work!'
                    : 'Time to focus on attendance'}
                </p>

                <p className="mt-2 text-sm leading-relaxed text-text-dim">
                  {attendanceStatus.description}
                </p>

                <div
                  className="mt-4 h-2 overflow-hidden rounded-full bg-surface-2"
                  role="progressbar"
                  aria-label="Overall attendance progress"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={attendance}
                >
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${attendanceStatus.barColor}`}
                    style={{ width: `${attendance}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="mt-6 border-t border-border-soft pt-4">
              <p className="text-xs leading-relaxed text-text-dim">
                This percentage is based on the attendance value returned by
                CoreSight. It does not represent a prediction or an estimate.
              </p>

              <Link
                to="/student/attendance"
                className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline"
              >
                View attendance records
                <span aria-hidden="true">→</span>
              </Link>
            </div>
          </Card>

          {/* Enrollment status */}
          <Card className="p-5 sm:p-6 lg:col-span-2">
            <h2 className="font-display text-lg font-semibold text-text">
              Face enrollment
            </h2>

            <p className="mt-1 text-sm text-text-dim">
              Your biometric enrollment status.
            </p>

            <div
              className={`mt-5 rounded-xl border p-4 ${
                record.faceEnrolled
                  ? 'border-verified/30 bg-verified/5'
                  : 'border-warning/30 bg-warning/5'
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl" aria-hidden="true">
                  {record.faceEnrolled ? '✓' : '⚠'}
                </span>

                <div>
                  <p className="text-sm font-semibold text-text">
                    {record.faceEnrolled
                      ? 'Enrollment complete'
                      : 'Enrollment required'}
                  </p>

                  <p className="mt-1 text-xs leading-relaxed text-text-dim">
                    {record.faceEnrolled
                      ? 'Your face enrollment is marked complete. You are ready for face-based attendance, subject to an active attendance session.'
                      : 'Complete face enrollment using your camera before participating in face-based attendance.'}
                  </p>
                </div>
              </div>
            </div>

            <Link
              to="/student/enrollment"
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 text-sm font-medium text-white transition hover:opacity-90"
            >
              {record.faceEnrolled
                ? 'View enrollment'
                : 'Start face enrollment'}
              <span aria-hidden="true">→</span>
            </Link>

            <p className="mt-3 text-xs leading-relaxed text-text-dim">
              Use a well-lit environment and follow the on-screen camera
              instructions during enrollment.
            </p>
          </Card>
        </section>

        {/* Quick links */}
        <section>
          <div className="mb-4">
            <h2 className="font-display text-lg font-semibold text-text">
              Quick actions
            </h2>
            <p className="mt-1 text-sm text-text-dim">
              Go directly to the student features you need.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Link to="/student/profile" className="group block">
              <Card className="h-full p-5 transition group-hover:border-accent/40">
                <span className="text-2xl" aria-hidden="true">
                  ◉
                </span>
                <h3 className="mt-4 text-sm font-semibold text-text">
                  My profile
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-dim">
                  View your personal information, contact details and academic
                  record.
                </p>
                <p className="mt-4 text-sm font-medium text-accent">
                  Open profile →
                </p>
              </Card>
            </Link>

            <Link to="/student/attendance" className="group block">
              <Card className="h-full p-5 transition group-hover:border-accent/40">
                <span className="text-2xl" aria-hidden="true">
                  ◷
                </span>
                <h3 className="mt-4 text-sm font-semibold text-text">
                  Attendance records
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-dim">
                  Open your attendance page to review the records available to
                  your account.
                </p>
                <p className="mt-4 text-sm font-medium text-accent">
                  View attendance →
                </p>
              </Card>
            </Link>

            <Link to="/student/enrollment" className="group block">
              <Card className="h-full p-5 transition group-hover:border-accent/40">
                <span className="text-2xl" aria-hidden="true">
                  ◎
                </span>
                <h3 className="mt-4 text-sm font-semibold text-text">
                  Face enrollment
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-dim">
                  Check your enrollment status or continue the camera
                  enrollment workflow.
                </p>
                <p className="mt-4 text-sm font-medium text-accent">
                  Open enrollment →
                </p>
              </Card>
            </Link>
          </div>
        </section>
      </div>
    </AppLayout>
  );
}
