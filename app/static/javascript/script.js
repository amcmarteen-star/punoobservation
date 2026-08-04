const signIn_form = document.getElementById('sign_in_form');

if(register_form){

    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirmPassword');
    const errorMessage = document.getElementById('error-message')

    register_form.addEventListener('submit', function(event){
        if (password.value !== confirmPassword.value){
            event.preventDefault();
            errorMessage.style.display = 'block';
        }else{
            errorMessage.style.display = 'none';
        }
    });
}
// const logIn_form = document.getElementById('log_in_form');

// if(logIn_form){

//     const username = document.getElementById('username');
//     const password = document.getElementById('password')
// }
