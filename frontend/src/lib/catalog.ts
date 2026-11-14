import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Amenity, AppConfig, School } from "../api/types";

const STATIC = { staleTime: 10 * 60_000, gcTime: 60 * 60_000 };

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => api<AppConfig>("/config"), ...STATIC });
}

export function useSchools() {
  return useQuery({ queryKey: ["schools"], queryFn: () => api<School[]>("/schools"), ...STATIC });
}

export function useAmenities() {
  return useQuery({ queryKey: ["amenities"], queryFn: () => api<Amenity[]>("/amenities"), ...STATIC });
}

export function useAmenityLabels(): (code: string) => string {
  const { data } = useAmenities();
  const map = new Map((data || []).map((a) => [a.code, a.label]));
  return (code: string) => map.get(code) || code;
}
