package com.ideascanner

import android.content.Context

object Storage {
    private const val PREF = "idea_prefs"
    private const val TOKEN = "token"

    fun saveToken(ctx: Context, token: String) {
        ctx.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().putString(TOKEN, token).apply()
    }
    fun getToken(ctx: Context): String? {
        return ctx.getSharedPreferences(PREF, Context.MODE_PRIVATE).getString(TOKEN, null)
    }
    fun clearToken(ctx: Context) {
        ctx.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().remove(TOKEN).apply()
    }
}
