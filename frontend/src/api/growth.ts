import client from './client';

export interface MonthlyBalance {
  month: string; // "YYYY-MM"
  categories: Record<string, number>;
}

export interface WeeklyLoad {
  week_start: string;
  avg_load: number;
}

export interface MonthlyBlockerCount {
  month: string;
  count: number;
}

export interface GrowthTrends {
  balance_trend: MonthlyBalance[];
  load_trend: WeeklyLoad[];
  blocker_trend: MonthlyBlockerCount[];
}

export async function getGrowthTrends(months = 3): Promise<GrowthTrends> {
  const res = await client.get<GrowthTrends>('/users/me/growth', {
    params: { months },
  });
  return res.data;
}
