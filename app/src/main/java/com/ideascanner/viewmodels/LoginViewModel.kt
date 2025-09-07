package com.ideascanner.viewmodels

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import com.ideascanner.ApiService
import com.ideascanner.models.User
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class LoginViewModel(private val apiService: ApiService) : ViewModel() {

    private val _loginResult = MutableLiveData<User?>()
    val loginResult: LiveData<User?> = _loginResult

    fun login(email: String, password: String) {
        val body = mapOf("email" to email, "password" to password)
        apiService.login(body).enqueue(object : Callback<Map<String, Any>> {
            override fun onResponse(
                call: Call<Map<String, Any>>,
                response: Response<Map<String, Any>>
            ) {
                if (response.isSuccessful) {
                    val data = response.body()
                    _loginResult.value = User(
                        id = (data?.get("id") as Double).toInt(),
                        name = data["name"].toString(),
                        email = data["email"].toString(),
                        token = data["token"]?.toString()
                    )
                } else {
                    _loginResult.value = null
                }
            }

            override fun onFailure(call: Call<Map<String, Any>>, t: Throwable) {
                _loginResult.value = null
            }
        })
    }
}
