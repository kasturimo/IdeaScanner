package com.ideascanner.models

data class User(
    val id: Int,
    val name: String,
    val email: String,
    val token: String?
)
